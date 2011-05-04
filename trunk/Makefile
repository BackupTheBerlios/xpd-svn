.SUFFIXES: .po .pot .mo

VERSION=$(shell cat VERSION)

# Default target - do nothing
all:
	@echo "Make one of the following targets:"
	@echo "	install		install the library and tools"
	@echo "	clean		remove all generated files"
	@echo "	update-po	update all po files with new strings from sources"
	@echo "	dist		make a distribution archive"

install:
	python setup.py install

win-install:
	rm -rf xpd-$(VERSION)
	mkdir xpd-$(VERSION)
	python setup.py install -O1 --root xpd-$(VERSION)
	mv xpd-$(VERSION)/usr/bin/xpd xpd-$(VERSION)/xpd.pyw
	mv xpd-$(VERSION)/usr/lib/python*/site-packages/xpdm xpd-$(VERSION)
	mv xpd-$(VERSION)/usr/share/locale xpd-$(VERSION)
	mv xpd-$(VERSION)/usr/share/xpd xpd-$(VERSION)/share
	rm -rf xpd-$(VERSION)/usr
	convert -background none xpd-$(VERSION)/share/xpd.svg -resize 64 xpd-$(VERSION)/xpd.ico

dist:
	rm -rf xpd-$(VERSION)
	mkdir xpd-$(VERSION) xpd-$(VERSION)/po \
	      xpd-$(VERSION)/share xpd-$(VERSION)/xpd \
	      xpd-$(VERSION)/build xpd-$(VERSION)/debian
	cp -a po/*.po* xpd-$(VERSION)/po
	cp -a share/*.glade share/*.svg xpd-$(VERSION)/share
	cp -a xpdm/*.py xpd-$(VERSION)/xpd
	cp -a build/xpd.desktop build/xpd.spec xpd-$(VERSION)/build
	cp -a debian/* xpd-$(VERSION)/debian
	cp -a Makefile COPYING README TRANSLATORS VERSION \
	      setup.py xpd xpd-$(VERSION)
	tar cvjf xpd-$(VERSION).tar.bz2 xpd-$(VERSION)
	rm -rf xpd-$(VERSION)

clean:
	python setup.py clean -a
	rm -f xpdm/*.pyc *.log
	rm -rf xpd-$(VERSION)

# Update translation files
update-po: $(wildcard po/*.po)

po/%.po: $(wildcard share/*.glade) $(wildcard xpdm/*.py) xpd
	@(xgettext --omit-header $(filter %.glade,$^) -o - ; \
	  xgettext --omit-header -L python $(filter-out %.glade,$^) -o -) | \
	msgmerge $@ - -o $@
