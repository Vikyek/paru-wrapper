NAME = paru-wrapper
VERSION = 1.1.1
PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin

.PHONY: all install uninstall test

all:

install:
	install -Dm755 paru-wrapper $(DESTDIR)$(BINDIR)/paru-wrapper
	install -Dm755 paru-wrapper-gittinator $(DESTDIR)$(PREFIX)/lib/paru-wrapper/paru-wrapper-gittinator
	install -Dm755 pacman-wrapper $(DESTDIR)$(BINDIR)/pacman-wrapper
	ln -sf $(BINDIR)/paru-wrapper $(DESTDIR)$(BINDIR)/paru

uninstall:
	rm -f $(DESTDIR)$(BINDIR)/paru-wrapper
	rm -f $(DESTDIR)$(PREFIX)/lib/paru-wrapper/paru-wrapper-gittinator
	rm -f $(DESTDIR)$(BINDIR)/pacman-wrapper
	rm -f $(DESTDIR)$(BINDIR)/paru

test:
	python3 -m unittest discover -b -s . -p "test_*.py"
