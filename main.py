#!/usr/bin/env python3
from ig_scraper.cli import Menu
from ig_scraper.core.utils import setup_signal_handler


def main():
    setup_signal_handler()
    menu = Menu()
    menu.run()


if __name__ == '__main__':
    main()