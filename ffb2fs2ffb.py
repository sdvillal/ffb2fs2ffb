#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Firefox bookmarks to filesystem and back.
This script provides 3 functions to:
  - Read a firefox bookmarks json file and put each container in a dir and each bookmark pickled in a ".ffurl" file.
  - Create a firefox bookmarks json file from an analogous directory hierarchy.
    It makes a best effort in order to map file properties (name, modification date) into bookmark information.
  - Open the URI inside a ".ffurl" file (essentially a pickled bookmark) inside the browser.

Associating .ffurl to this script would allow fast opening of bookmarks inside firefox.

All this for what? I like to organize my oversized bookmarks list using a two-panel ofm to move things around.
"""
from copy import deepcopy
import os
import os.path as op
import shutil
import cPickle as pickle
import unicodedata
import json
import re
import sys
import datetime
import inspect
from argh import *

print '----FFB2FS2FFB: FireFox Bookmarks to the File System and back'
print '    See: http://github.com/sdvillal/ffb2fs2ffb'
sys.stdout.flush()

TEST_DIR = op.join(op.realpath(op.dirname(__file__)), 'test-data')
TEST_BOOKMARKS_FILEPATH = op.join(TEST_DIR, 'bookmarks-2013-02-20.json')
TEST_DESTDIR_PATH = op.join(TEST_DIR, 'ff2fs_test')
TEST_DESTBOOKMARKS_FILEPATH = op.join(TEST_DIR, 'reconstructed-bookmarks.json')
CONTAINER_FILE_NAME = '__info__.ffcontainer'

############################
#---- Supporting functions
############################

def ensure_writable_dir(path):
    """Ensures that a path is a writable directory."""
    if op.exists(path):
        if not op.isdir(path):
            raise Exception('%s exists but it is not a directory' % path)
        if not os.access(path, os.W_OK):
            raise Exception('%s is a directory but it is not writable' % path)
    else:
        os.makedirs(path)


def slugify(value, max_filename_length=200):
    """Create a valid filename from a bookmark title by:
      - Normalizing the string (see http://unicode.org/reports/tr15/)
      - Converting it to lowercase
      - Removing non-alpha characters
      - Converting spaces to hyphens
    Adapted from:
      - http://stackoverflow.com/questions/5574042/string-slugification-in-python
      - http://stackoverflow.com/questions/295135/turn-a-string-into-a-valid-filename-in-python
    See too: http://en.wikipedia.org/wiki/Comparison_of_file_systems#Limits.
    """
    value = unicode(value)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
    value = unicode(re.sub('[^\w\s-]', '', value).strip().lower())
    value = unicode(re.sub('[-\s]+', '-', value))
    if len(value) > max_filename_length:
        return value[:max_filename_length]
    return value


def prtime2datetime(prtime):
    """Converts a PRTime date stamp to python's datetime.
    See: https://developer.mozilla.org/en/docs/PRTime.

    Examples
    --------
    >>> prtime = 1231857403576669
    >>> dt = prtime2datetime(prtime)
    >>> dt
    datetime.datetime(2009, 1, 13, 14, 36, 43, 576669)
    """
    return datetime.datetime(1970, 1, 1) + datetime.timedelta(microseconds=prtime)


def datetime2prtime(adatetime):
    """Converts a python's datetime into a PRTime date stamp.

    Examples
    --------
    >>> prtime = 1231857403576669
    >>> datetime2prtime(prtime2datetime(prtime))
    1231857403576669
    """

    def td_to_microseconds(td):
        """Converts a datetime.timedelta to microseconds."""
        return td.days * 24 * 60 * 60 * 1000000 + \
               td.seconds * 1000000 + \
               td.microseconds

    return td_to_microseconds(adatetime - datetime.datetime(1970, 1, 1))


def node_filename(node):
    """Returns a valid filename based on a bookmark title and its id."""
    return '%s__ffid=%s' % (slugify(node['title']), node['id'])


def generate_container_dict(
        title=None,
        description=None,
        container_id=None,
        dateAdded=None,
        lastModified=None,
        root=None,
        index=None,
        parent=None,
        annos=None,
        children=None):
    """Generates a container dictionary with the specified information."""
    translator = {'container_id': 'id'}
    container = {'type': 'text/x-moz-place-container'}
    for key, val in locals().iteritems():
        if not key in ('translator', 'container') and val is not None:
            container[translator.get(key, key)] = val
    return container


def is_bookmark(node):
    return node.get('type', None) == 'text/x-moz-place'


def is_container(node):
    return node.get('type', None) == 'text/x-moz-place-container'


def traverse_tree(root, nodef):
    """DFS traversal of the bookmarks tree.
    If the nodef function has arity 2, the parent is passed to the function too.
    """
    args, _, _, _ = inspect.getargspec(nodef)
    if 1 == len(args):
        def traverse_without_parent(root):
            nodef(root)
            for child in root.get('children', ()):
                traverse_without_parent(child)
        traverse_without_parent(root)
    else:
        def traverse_with_parent(root, parent):
            nodef(root, parent)
            for child in root.get('children', ()):
                traverse_with_parent(child, root)
        traverse_with_parent(root, None)


def present_ids(root, all_must_have_id=False, all_must_be_unique=False):
    """Returns all the different node ids present in the bookmarks tree."""
    nids = set()

    def add_id(node):
        nid = node.get('id', None)
        if all_must_have_id and not nid:
            raise Exception('Found a node without ID! %r' % node)
        if all_must_be_unique and nid in nids:
            raise Exception('Found a repeated ID! %s' % nid)
        nids.add(nid)

    traverse_tree(root, add_id)
    return nids


def uniquify_ids(root):
    """Makes each node to have a unique ID. Ignores previous IDs."""
    root = deepcopy(root)
    last_assigned = [2]

    def assign_id(node, parent):
        node['id'] = last_assigned[0]  #Missing python 3 nonlocal...
        if parent:
            node['parent'] = parent['id']
        last_assigned[0] += 1

    traverse_tree(root, assign_id)
    return root


def present_keys(root, process_containers=True, process_bookmarks=True):
    """Returns all the present keys in the bookmarks tree."""
    keys = set()

    def add_key(node):
        if process_containers and is_container(node) or process_bookmarks and is_bookmark(node):
            keys.update(node.keys())

    traverse_tree(root, add_key)
    return keys

############################
#---- Firefox bookmarks json -> filesystem hierarchy
############################
def bookmarks2dir(bookmarks_file=TEST_BOOKMARKS_FILEPATH,
                  dest_dir=TEST_DESTDIR_PATH,
                  delete_all_first=False,
                  overwrite=False):
    """Mirrors a firefox bookmarks json file into the file-system, one dir per container, one file per bookmark."""

    print 'Mirroring bookmarks from\n\t%s\nto\n\t%s'%(bookmarks_file, dest_dir)

    if not op.isfile(bookmarks_file):
        raise Exception('Cannot find bookmarks file: %s' % bookmarks_file)

    #Delete the root_dir
    if op.isdir(dest_dir):
        print 'Warning: root dir \"%s\" already exists' % dest_dir
    if delete_all_first and op.isdir(dest_dir):
        print 'Removing the root dir \"%s\"' % dest_dir
        shutil.rmtree(dest_dir)

    def build_tree(entry, root_dir, seen_ids):
        """Traverses the FFs bookmark tree, mirroring its structure in the file-system."""

        def check_id_uniqueness(entry):
            entry_id = entry.get('id', None)
            if entry_id is None:
                raise Exception('Found an entry without id!')
            if entry_id in seen_ids:
                raise Exception('id %s is not unique' % entry_id)
            seen_ids.add(entry_id)

        #Write the container node
        if not is_container(entry):
            raise Exception('The entry type for %s must be a moz-place-container' % entry.get('id', '!!unknownid!!'))
        check_id_uniqueness(entry)
        container_file = op.join(root_dir, CONTAINER_FILE_NAME)
        if op.exists(container_file) and not overwrite:
            raise Exception('The container file %s already exists. Please, change \"overwrite\" or delete dest_dir.')
        ensure_writable_dir(root_dir)
        children = entry.get('children', ())
        entry['children'] = ()
        with open(container_file, 'w') as writer:
            pickle.dump(entry, writer)
        #Process children
        for child in children:
            if is_container(child):
                build_tree(child, op.join(root_dir, node_filename(child)), seen_ids)
            elif is_bookmark(child):
                check_id_uniqueness(child)
                if child.get('children', None):
                    raise Exception('A moz-place node should have no children, but \"%s\" has' % child['title'])
                ffurl = op.join(root_dir, node_filename(child) + '.ffurl')
                with open(ffurl, 'w') as writer:
                    pickle.dump(child, writer)
            else:
                raise Exception('Unknown bookmark type %r for entry \"%s\"' % (child.get('type', 'unknown'),
                                                                               child['title']))

    #Mirror the bookmarks structure into the hard disk
    with open(bookmarks_file) as reader:
        build_tree(json.load(reader), dest_dir, set())

    print 'Done!'

############################
#---- Filesystem hierarchy -> firefox bookmarks
############################
def dir2bookmarks(src_dir=TEST_DESTDIR_PATH,
                  dest_bookmarks_file=TEST_DESTBOOKMARKS_FILEPATH):
    """Takes a directory and mirrors its structure into firefox bookmarks json."""

    print 'Mirroring bookmarks from\n\t%s\nto\n\t%s'%(src_dir, dest_bookmarks_file)

    def update_title(fn, entry):
        if op.basename(fn).partition('__')[0] != slugify(entry['title']):
            entry['title'] = op.basename(fn).partition('__')[0].replace('\"', '\'')

    def read_container(root_dir):
        if not op.isdir(root_dir):
            raise Exception('%s should be a directory, but it is not' % root_dir)
        container_file = op.join(root_dir, CONTAINER_FILE_NAME)
        if op.exists(container_file):
            with open(container_file) as reader:
                this_container = pickle.load(reader)
        else:
            this_container = generate_container_dict(
                title=op.basename(root_dir),
                dateAdded=datetime2prtime(datetime.datetime.fromtimestamp(op.getmtime(root_dir))),
                lastModified=datetime2prtime(datetime.datetime.fromtimestamp(op.getctime(root_dir))))
        ff_children = []
        fs_children = [op.join(root_dir, fn) for fn in os.listdir(root_dir)]
        fs_children.sort(key=op.getmtime)
        for fs_child in fs_children:
            if op.isdir(fs_child):
                ff_children.append(read_container(fs_child))
            elif fs_child.endswith('.ffurl'):
                with open(fs_child) as reader:
                    bookmark = pickle.load(reader)
                    update_title(fs_child, bookmark)
                    ff_children.append(bookmark)
        this_container['children'] = ff_children
        update_title(root_dir, this_container)
        return this_container

    #Very simple, read the dirs and files into a dict, jsondumpit
    with open(dest_bookmarks_file, 'w') as writer:
        json.dump(uniquify_ids(read_container(src_dir)),
                  writer,
                  ensure_ascii=True,
                  separators=(',', ':'),
                  check_circular=True)

    print 'Done!'

############################
#---- Open a pickled ffurl in firefox
############################
def open_ffurl(ffurl):
    """Opens the URI in a .ffurl bookmark file inside the browser."""
    with open(ffurl) as reader:
        entry = pickle.load(reader)
    os.system('firefox %s' % entry['uri'])


if __name__ == '__main__':
    dispatch_commands([bookmarks2dir, dir2bookmarks, open_ffurl])

######
# Notes:
#   - only tried with bookmarks out of FF 17. Is there any spec for the FF bookmarks format?
#   - icons are not preserved, they are meant to be in the sqlite DB, do not bother
#   - warn that at the moment first level directories cannot be created
#   - make sure that special directories have the corresponding ID (seems it does not matter). Read it here
#    * http://code.crapouillou.net/projects/chrome-syncplaces/wiki
#   - somebody looking for something similar:
#    * http://stackoverflow.com/questions/2034373/python-cli-to-edit-firefox-bookmarks
#######