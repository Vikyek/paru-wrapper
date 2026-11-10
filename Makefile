NAME = paru-wrapper
VERSION = 1.2.0
PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin
MANDIR ?= $(PREFIX)/share/man/man1
LIBDIR ?= $(PREFIX)/lib/paru-wrapper

.PHONY: all install uninstall test

all:

install:
	install -Dm755 paru-wrapper $(DESTDIR)$(BINDIR)/paru-wrapper
	install -Dm755 paru-wrapper-gittinator $(DESTDIR)$(LIBDIR)/paru-wrapper-gittinator
	install -Dm755 paru-wrapper-gittinator-impl $(DESTDIR)$(LIBDIR)/paru-wrapper-gittinator-impl
	install -Dm755 pacman-wrapper $(DESTDIR)$(BINDIR)/pacman-wrapper
	install -Dm755 update_mkvpkg_aur.py $(DESTDIR)$(BINDIR)/update_mkvpkg_aur.py
	install -Dm644 man1/paru-wrapper.1 $(DESTDIR)$(MANDIR)/paru-wrapper.1
	install -d $(DESTDIR)$(LIBDIR)/plugins.d
	install -Dm755 default-plugins/*.sh $(DESTDIR)$(LIBDIR)/plugins.d/
	ln -sf $(BINDIR)/paru-wrapper $(DESTDIR)$(BINDIR)/paru

uninstall:
	rm -f $(DESTDIR)$(BINDIR)/paru-wrapper
	rm -f $(DESTDIR)$(LIBDIR)/paru-wrapper-gittinator
	rm -f $(DESTDIR)$(LIBDIR)/paru-wrapper-gittinator-impl
	rm -f $(DESTDIR)$(BINDIR)/pacman-wrapper
	rm -f $(DESTDIR)$(BINDIR)/update_mkvpkg_aur.py
	rm -f $(DESTDIR)$(MANDIR)/paru-wrapper.1
	rm -rf $(DESTDIR)$(LIBDIR)
	rm -f $(DESTDIR)$(BINDIR)/paru

test:
	python3 -m unittest discover -b -s . -p "test_*.py"
