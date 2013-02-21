# ffb2fs2ffb: Firefox Bookmarks to File System and Back

Ever wanted to organize your oversized bookmarks list using the same tools you use to organize files?
That was the only good feature of internet explorer...

## Instalation

This [python](http://www.python.org) script depends on [argh argparse](https://pypi.python.org/pypi/argh).
Just *sudo easy_install argh* or *pip install argh* it.

## Usage

This script provides three commands allowing to:

* Read a firefox bookmarks json file and store the bookmarks structure under a directory hierarchy.

Inside Firefox:
Bookmarks -> Show All Bookmarks -> Import and Backup -> Backup

Command:
python ffb2fs2ffb.py bookmarks2dir --bookmarks_file <file-saved-from-firefox> --dest_dir <destination-directory>

* Read a directory hierarchy into a firefox bookmarks json that can be imported back to firefox

Command:
python ffb2fs2ffb.py dir2bookmarks --src_dir <directory-with-bookmarks> --dest <destination-json-to-load-on-firefox>

Inside Firefox:
Bookmarks -> Show All Bookmarks -> Import and Backup -> Restore -> Choose File

* Open a .ffurl file in firefox (assuming that firefox is in the PATH).
This comes handy if, for example, one associates this command with the ".ffurl" files to open them from a file manager.

Command:
python ffb2fs2ffb.py open-ffurl --ffurl <ffurl-file>
-or-
ffurl-open.bash <ffurl-file>

## Features and Limitations

- The json -> dir function has no known limitations. Favicons are lost (as these are stored elsewhere).

- The names of the exported bookmarks are ugly - a concession to avoid filesystem problems.
  No worries, the original names are still kept inside the file.

- The script supports
    - copying and moving: just copy / move .ffurl files and directories around; symlinking also works.
    - renaming: just change the name to a .ffurl file or a directory
    - creation of new containers: just create new directies
      (but *not* directly under the first level, that is, where the "Bookmarks Menu" directory is).

- The dir -> json function will make a best effort to get everything correct. But please, *do backup your bookmarks*.

## Face the truth

Perhaps you should consider stop bookmarking everything - really, you are never gonna come back...