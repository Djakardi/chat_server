"""
TUI чат-клиент.

Запуск:
    cd src && python chat_tui.py

Переменные окружения:
    MNEMONIC   — мнемоника пользователя (обязательна)
    HOST       — адрес сервера (по умолчанию: localhost)
    PORT       — порт сервера  (по умолчанию: 8080)
    PEER_ADDR  — hex-ключ собеседника (можно задать в UI)
"""

import asyncio
import logging
import os
import ssl
import shutil
import subprocess  # nosec B404
import sys

sys.path.insert(0, os.path.dirname(__file__))

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Header, Footer, RichLog, Input, Label, Static
from textual.binding import Binding

from dispatcher import Dispatcher
from client.client import Client
from proto.packages import PingRequest, MessageRequest, MessageResponse

logging.disable(logging.CRITICAL)  # не загрязняем TUI логами

HOST = os.getenv("HOST", "aganimchat.tech")
PORT = int(os.getenv("PORT", "443"))
MNEMONIC = os.getenv("MNEMONIC", "")
PEER_ADDR = os.getenv("PEER_ADDR", "")

print(HOST, PORT)


# ── dispatcher для входящих сообщений ────────────────────────────────────────


def make_dispatcher(app: "ChatApp") -> Dispatcher:
    dp = Dispatcher()

    @dp.register(PingRequest)
    async def ping(package: PingRequest, client: Client):
        return PingRequest(
            request_id=package.request_id,
            from_addr=client.crypto.public_key_bytes,
        )

    @dp.register(MessageRequest)
    async def on_message(package: MessageRequest, client: Client):
        try:
            text = client.crypto.decrypt_message(package.payload).decode("utf-8")
        except Exception:
            text = "<не удалось расшифровать>"

        sender = package.from_addr.hex()[:16] + "..."
        app.post_message(IncomingMessage(sender=sender, text=text))

        return MessageResponse(
            request_id=package.request_id,
            from_addr=client.crypto.public_key_bytes,
            is_delivered=True,
        )

    return dp


# ── Textual message для передачи между asyncio и UI ──────────────────────────

from textual.message import Message as TextualMessage


class IncomingMessage(TextualMessage):
    def __init__(self, sender: str, text: str):
        super().__init__()
        self.sender = sender
        self.text = text


class StatusUpdate(TextualMessage):
    def __init__(self, text: str):
        super().__init__()
        self.text = text


# ── Главное приложение ────────────────────────────────────────────────────────


class ChatApp(App):
    CSS = """
    Screen {
        layout: vertical;
    }
    #log {
        border: solid $primary;
        height: 1fr;
        margin: 0 1;
    }
    #status {
        height: 1;
        margin: 0 1;
        color: $text-muted;
    }
    #peer-row {
        height: 3;
        margin: 0 1;
    }
    #peer-input {
        width: 1fr;
    }
    #msg-input {
        margin: 0 1 1 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Выйти"),
        Binding("ctrl+q", "quit", "Выйти"),
        Binding("ctrl+y", "copy_pubkey", "Копировать ключ"),
        Binding("ctrl+g", "paste_pubkey", "Вставить ключ"),
    ]

    def __init__(self, mnemonic: str, peer_addr: str):
        super().__init__()
        self._mnemonic = mnemonic
        self._peer_addr = peer_addr
        self._client: Client | None = None
        self._copyq_path = shutil.which("copyq")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield RichLog(id="log", markup=True, wrap=True)
        yield Static("", id="status")
        yield Horizontal(
            Label(" Peer: ", classes="label"),
            Input(
                placeholder="hex pubkey собеседника",
                value=self._peer_addr,
                id="peer-input",
            ),
            id="peer-row",
        )
        yield Input(placeholder="Сообщение... (Enter — отправить)", id="msg-input")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#msg-input", Input).focus()
        self.run_worker(self._connect(), exclusive=True, name="connect")

    def _read_clipboard(self) -> str:
        value = (self.clipboard or "").strip()
        if value:
            return value

        # Fallback для терминалов, где Textual clipboard не синхронизирован.
        try:
            if not self._copyq_path:
                return ""
            proc = subprocess.run(  # nosec B603
                [self._copyq_path, "clipboard"],  # nosec B603,B607
                check=True,
                capture_output=True,
                text=True,
                timeout=1,
            )
            return proc.stdout.strip()
        except (subprocess.SubprocessError, OSError):
            return ""

    def _write_clipboard(self, value: str) -> None:
        self.copy_to_clipboard(value)
        try:
            if not self._copyq_path:
                return
            subprocess.run(  # nosec B603
                [self._copyq_path, "copy", value],  # nosec B603,B607
                check=True,
                capture_output=True,
                text=True,
                timeout=1,
            )
        except (subprocess.SubprocessError, OSError):
            return

    # ── события ──────────────────────────────────────────────────────────────

    def on_incoming_message(self, event: IncomingMessage) -> None:
        log = self.query_one("#log", RichLog)
        log.write(f"[cyan]{event.sender}[/cyan]: {event.text}")

    def on_status_update(self, event: StatusUpdate) -> None:
        self.query_one("#status", Static).update(event.text)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "msg-input":
            await self._send(event.value.strip())
            event.input.clear()
        elif event.input.id == "peer-input":
            self._peer_addr = event.value.strip()
            self.query_one("#msg-input", Input).focus()

    # ── логика ───────────────────────────────────────────────────────────────

    async def _connect(self) -> None:
        log = self.query_one("#log", RichLog)
        self.post_message(StatusUpdate("Подключение..."))
        try:
            # Decide whether to use SSL: default ports 443 and 8443 are treated as SSL.
            use_ssl_env = os.getenv("USE_SSL", "").lower() in ("1", "true", "yes")
            use_ssl = use_ssl_env or PORT in (443, 8443)

            ssl_ctx = None
            if use_ssl:
                # Allow opting out of verification for self-signed certs during testing
                insecure = os.getenv("INSECURE_SSL", "").lower() in ("1", "true", "yes")
                if insecure:
                    ssl_ctx = ssl.create_default_context()
                    ssl_ctx.check_hostname = False
                    ssl_ctx.verify_mode = ssl.CERT_NONE
                else:
                    ssl_ctx = ssl.create_default_context()

            client = await Client.connect(
                host=HOST,
                port=PORT,
                mnemonic=self._mnemonic,
                ssl_ctx=ssl_ctx,
                server_hostname=HOST,
            )
            client.setup_handler(make_dispatcher(self))
            self._client = client
        except Exception as e:
            log.write(f"[red]Ошибка подключения: {e}[/red]")
            self.post_message(StatusUpdate("Не подключён"))
            return

        my_key = self._client.crypto.public_key
        log.write(f"[green]Подключён![/green] Ваш ключ:")
        log.write(f"[bold]{my_key}[/bold]")
        self.post_message(StatusUpdate(f"Подключён · {HOST}:{PORT}"))

        # ждём разрыва соединения
        await self._client.wait_loop()
        self.post_message(StatusUpdate("Соединение разорвано"))
        log.write("[yellow]Соединение разорвано[/yellow]")

    async def _send(self, text: str) -> None:
        log = self.query_one("#log", RichLog)

        if not text:
            return

        peer = self.query_one("#peer-input", Input).value.strip()
        if not peer:
            log.write("[red]Укажите hex-ключ собеседника[/red]")
            return

        if self._client is None:
            log.write("[red]Нет соединения с сервером[/red]")
            return

        try:
            await self._client.send_message(to_addr=peer, payload=text.encode("utf-8"))
            log.write(f"[green]Вы[/green]: {text}")
        except Exception as e:
            log.write(f"[red]Ошибка отправки: {e}[/red]")

    async def action_quit(self) -> None:
        if self._client:
            self._client.disconnect()
        self.exit()

    def action_copy_pubkey(self) -> None:
        log = self.query_one("#log", RichLog)
        if self._client is None:
            log.write("[red]Сначала подключитесь к серверу[/red]")
            self.post_message(StatusUpdate("Ключ не скопирован: нет соединения"))
            return

        pubkey = self._client.crypto.public_key
        self._write_clipboard(pubkey)
        self.post_message(StatusUpdate("Публичный ключ скопирован в буфер"))
        log.write("[green]Публичный ключ скопирован (Ctrl+Y)[/green]")

    async def action_paste_pubkey(self) -> None:
        log = self.query_one("#log", RichLog)
        peer_input = self.query_one("#peer-input", Input)

        value = self._read_clipboard()
        if not value:
            log.write("[red]Буфер обмена пуст (Textual/copyq)[/red]")
            self.post_message(StatusUpdate("Ключ не вставлен: буфер пуст"))
            return

        try:
            key = bytes.fromhex(value)
            if len(key) != 33:
                raise ValueError("invalid pubkey length")
        except ValueError:
            log.write("[red]В буфере невалидный публичный ключ[/red]")
            self.post_message(StatusUpdate("Ключ не вставлен: невалидный формат"))
            return

        peer_input.value = value
        self._peer_addr = value
        self.query_one("#msg-input", Input).focus()
        self.post_message(StatusUpdate("Ключ собеседника вставлен из буфера"))
        log.write("[green]Ключ собеседника вставлен (Ctrl+G)[/green]")


# ── точка входа ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not MNEMONIC:
        print("Задайте переменную окружения MNEMONIC")
        print("Пример:")
        print('  MNEMONIC="word1 word2 ... word12" python src/chat_tui.py')
        sys.exit(1)

    ChatApp(mnemonic=MNEMONIC, peer_addr=PEER_ADDR).run()
