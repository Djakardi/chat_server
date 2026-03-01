from .server import Server


def main():
    server = Server()
    server.run_loop()


if __name__ == "__main__":
    main()
