PREFIX ?= /usr
BINDIR ?= $(PREFIX)/bin

.PHONY: all install uninstall

all:

install:
	install -Dm755 paru-wrapper $(DESTDIR)$(BINDIR)/paru-wrapper
	install -Dm755 update_mkvpkg_aur.py $(DESTDIR)$(BINDIR)/update_mkvpkg_aur.py

uninstall:
	rm -f $(DESTDIR)$(BINDIR)/paru-wrapper
	rm -f $(DESTDIR)$(BINDIR)/update_mkvpkg_aur.py
