# -*- mode: python; coding: utf-8 -*-
# Copyright 2014 Peter Williams <peter@newton.cx>
# Licensed under the GNU General Public License, version 3 or higher.

"""Core bibliographic routines.

Generic things dealing with names, identifiers, etc.

We store names like so:
  "Albert J. von_Trapp_Rodolfo,_Jr."
As far as I can see, this makes it easy to pull out surnames and deal with all
that mess. We're pretty boned once I start dealing with papers whose have
author names given in both Latin and Chinese characters, though.

Another thing to be wary of is "names" like "The Fermi-LAT Collaboration".
Some Indians have only single names (e.g. "Gopal-Krishna").

NFAS = normalized first-author surname. We decapitalize, remove accents, and
replace nonletters with periods, so it's a gmail-ish form.

"""

__all__ = ('parse_name encode_name normalize_surname '
           'classify_pub_ref doi_to_maybe_bibcode autolearn_pub '
           'print_generic_listing parse_search').split ()

import re
from . import *


def parse_name (text):
    given, family = text.rsplit (' ', 1)
    return given, family.replace ('_', ' ')


def encode_name (given, family):
    return given + ' ' + family.replace (' ', '_')


def normalize_surname (name):
    from unicodedata import normalize
    # this strips accents:
    name = normalize ('NFKD', unicode (name)).encode ('ascii', 'ignore')
    # now strip non-letters and condense everything:
    return re.sub (r'\.\.+', '.', re.sub (r'[^a-z]+', '.', name.lower ()))


_arxiv_re_1 = re.compile (r'^\d\d[01]\d\.\d+')
_arxiv_re_2 = re.compile (r'^[a-z-]+/\d+')
_bibcode_re = re.compile (r'^\d\d\d\d[a-zA-Z0-9&]+')
_doi_re = re.compile (r'^10\.\d+/.*')
_fasy_re = re.compile (r'.*\.(\d+|\*)$')

def classify_pub_ref (text):
    """Given some text that we believe identifies a publication, try to
    figure out how it does so."""

    if text.startswith ('doi:'):
        return 'doi', text[4:]

    if _doi_re.match (text) is not None:
        return 'doi', text

    if _bibcode_re.match (text) is not None:
        return 'bibcode', text

    if _arxiv_re_1.match (text) is not None:
        return 'arxiv', text

    if _arxiv_re_2.match (text) is not None:
        return 'arxiv', text

    if text.startswith ('arxiv:'):
        return 'arxiv', text[6:]

    if _fasy_re.match (text) is not None:
        # This test should go very low since it's quite open-ended.
        surname, year = text.rsplit ('.', 1)
        return 'nfasy', normalize_surname (surname) + '.' + year

    return 'nickname', text


def doi_to_maybe_bibcode (doi):
    from webutil import urlquote, urlopen

    bibcode = None

    # XXX could convert this to an ADS 2.0 record search, something like
    # http://adslabs.org/adsabs/api/record/{doi}/?dev_key=...

    url = ('http://adsabs.harvard.edu/cgi-bin/nph-abs_connect?'
           'data_type=Custom&format=%25R&nocookieset=1&doi=' +
           urlquote (doi))
    lastnonempty = None

    for line in urlopen (url):
        line = line.strip ()
        if len (line):
            lastnonempty = line

    if lastnonempty is None:
        return None
    if lastnonempty.startswith ('Retrieved 0 abstracts'):
        return None

    return lastnonempty


def autolearn_pub (text):
    kind, text = classify_pub_ref (text)

    if kind == 'doi':
        # ADS seems to have better data quality.
        bc = doi_to_maybe_bibcode (text)
        if bc is not None:
            print '[Associated', text, 'to', bc + ']'
            kind, text = 'bibcode', bc

    if kind == 'doi':
        from crossref import autolearn_doi
        return autolearn_doi (text)

    if kind == 'bibcode':
        from ads import autolearn_bibcode
        return autolearn_bibcode (text)

    if kind == 'arxiv':
        return autolearn_arxiv (text)

    die ('cannot auto-learn publication "%s"', text)


def print_generic_listing (db, pub_seq):
    info = []
    maxnfaslen = 0
    maxnicklen = 0

    # TODO: number these, and save the results in a table so one can write
    # "bib read %1" to read the top item of the most recent listing.

    for pub in pub_seq:
        nfas = pub.nfas or '(no author)'
        year = pub.year or '????'
        title = pub.title or '(no title)'
        nick = db.choose_pub_nickname (pub.id) or ''

        if isinstance (year, int):
            year = '%04d' % year

        info.append ((nfas, year, title, nick))
        maxnfaslen = max (maxnfaslen, len (nfas))
        maxnicklen = max (maxnicklen, len (nick))

    ofs = maxnfaslen + maxnicklen + 9

    for nfas, year, title, nick in info:
        print '%*s.%s  %*s  ' % (maxnfaslen, nfas, year, maxnicklen, nick),
        print_truncated (title, ofs)


# Searching

def parse_search (interms):
    """We go to the trouble of parsing searches ourselves because ADS's syntax
    is quite verbose. Terms we support:

    (integer) -> year specification
       if this year is 2014, 16--99 are treated as 19NN,
       and 00--15 is treated as 20NN (for "2015 in prep" papers)
       Otherwise, treated as a full year.
    """

    outterms = []
    bareword = None

    from time import localtime
    thisyear = localtime ()[0]
    next_twodigit_year = (thisyear + 1) % 100

    for interm in interms:
        try:
            asint = int (interm)
        except ValueError:
            pass
        else:
            if asint < 100:
                if asint > next_twodigit_year:
                    outterms.append (('year', asint + (thisyear // 100 - 1) * 100))
                else:
                    outterms.append (('year', asint + (thisyear // 100) * 100))
            else:
                outterms.append (('year', asint))
            continue

        # It must be the bareword
        if bareword is None:
            bareword = interm
            continue

        die ('searches only support a single "bare word" right now')

    if bareword is not None:
        outterms.append (('surname', bareword)) # note the assumption here

    return outterms