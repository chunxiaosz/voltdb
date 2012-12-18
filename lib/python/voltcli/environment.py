# This file is part of VoltDB.

# Copyright (C) 2008-2012 VoltDB Inc.
#
# This file contains original code and/or modifications of original code.
# Any modifications made by VoltDB Inc. are licensed under the following
# terms and conditions:
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

# Provides global meta-data that is derived from the environment.

__author__ = 'scooper'

import sys
import os
import glob
import re
import shlex

from voltcli import utility

re_voltdb_jar = re.compile('^voltdb(client)?-[.0-9]+[.]jar$')

# Filled in during startup.
standalone   = None
version      = None
command_dir  = None
command_name = None
voltdb_jar   = None
classpath    = None

# Assume that we're in a subdirectory of the main volt Python library
# directory.  Add the containing library directory to the Python module load
# path so that verb modules can import any module here. E.g.:
#   from voltcli import <module>...
volt_python = os.path.dirname(os.path.dirname(__file__))
if volt_python not in sys.path:
    sys.path.insert(0, volt_python)

# Java configuration
if 'JAVA_HOME' in os.environ:
    java = os.path.join(os.environ['JAVA_HOME'], 'bin', 'java')
else:
    java = utility.find_in_path('java')
if not java:
    utility.abort('Could not find java in environment, set JAVA_HOME or put java in the path.')
java_opts = []
if 'JAVA_HEAP_MAX' in os.environ:
    java_opts.append(os.environ.get('JAVA_HEAP_MAX'))
if 'VOLTDB_OPTS' in os.environ:
    java_opts.extend(shlex.split(os.environ['VOLTDB_OPTS']))
if 'JAVA_OPTS' in os.environ:
    java_opts.extend(shlex.split(os.environ['JAVA_OPTS']))
if not [opt for opt in java_opts if opt.startswith('-Xmx')]:
    java_opts.append('-Xmx1024m')

def initialize(standalone_arg, command_name_arg, command_dir_arg, version_arg):
    """
    Set the VOLTDB_LIB and VOLTDB_VOLTDB environment variables based on the
    script location and the working directory.
    """
    global command_name, command_dir, version
    command_name = command_name_arg
    command_dir = command_dir_arg
    version = version_arg

    # Stand-alone scripts don't need a development environment.
    global standalone
    standalone = standalone_arg
    if standalone:
        return

    # Add the working directory, the command directory, and VOLTCORE as
    # starting points for the scan.
    dirs = []
    def add_dir(dir):
        if dir and os.path.isdir(dir) and dir not in dirs:
            dirs.append(os.path.realpath(dir))
    add_dir(os.getcwd())
    add_dir(os.path.realpath(command_dir))
    add_dir(os.path.realpath(os.environ.get('VOLTCORE', None)))
    utility.verbose_info('Base directories for scan:', dirs)

    lib_search_globs    = set()
    voltdb_search_globs = set()

    voltdb_lib    = os.environ.get('VOLTDB_LIB', '')
    voltdb_voltdb = os.environ.get('VOLTDB_VOLTDB', '')

    for dir in dirs:

        # Crawl upward and look for the lib and voltdb directories.
        # They may be the same directory when installed by a Linux installer.
        # Set the VOLTDB_... environment variables accordingly.
        # Also locate the voltdb jar file.
        global voltdb_jar
        while (dir and dir != '/' and (not voltdb_lib or not voltdb_voltdb or not voltdb_jar)):
            utility.debug('Checking potential VoltDB root directory: %s' % os.path.realpath(dir))

            # Try to set VOLTDB_LIB if not set.
            if not voltdb_lib:
                for subdir in ('lib', os.path.join('lib', 'voltdb')):
                    glob_chk = os.path.join(dir, subdir, 'zmq*.jar')
                    lib_search_globs.add(glob_chk)
                    if glob.glob(glob_chk):
                        voltdb_lib = os.path.join(dir, subdir)
                        os.environ['VOLTDB_LIB'] = voltdb_lib
                        utility.debug('VOLTDB_LIB=>%s' % voltdb_lib)

            # Try to set VOLTDB_VOLTDB if not set. Look for the voltdb jar file.
            if not voltdb_voltdb or not voltdb_jar:
                voltdb_dirs = []
                # Search for voltdb jar starting with VOLTDB_VOLTDB environment variable.
                if voltdb_voltdb:
                    voltdb_dirs.append(voltdb_voltdb)
                # Then search the voltdb and lib/voltdb subdirectories of the scan directory.
                # The lib/voltdb subdir is needed for the package installation file layout.
                voltdb_dirs.append(os.path.join(dir, 'voltdb'))
                voltdb_dirs.append(os.path.join(dir, 'lib', 'voltdb'))
                for voltdb_dir in voltdb_dirs:
                    glob_chk = os.path.join(voltdb_dir,  'voltdb-*.jar')
                    voltdb_search_globs.add(glob_chk)
                    for voltdb_jar_chk in glob.glob(glob_chk):
                        if re_voltdb_jar.match(os.path.basename(voltdb_jar_chk)):
                            voltdb_jar = voltdb_jar_chk
                            utility.debug('VoltDB jar: %s' % voltdb_jar)
                            if not voltdb_voltdb:
                                voltdb_voltdb = os.path.dirname(voltdb_jar)
                                os.environ['VOLTDB_VOLTDB'] = voltdb_voltdb
                                utility.debug('VOLTDB_VOLTDB=>%s' % voltdb_voltdb)

            dir = os.path.dirname(dir)

    # If the VoltDB jar was found then VOLTDB_VOLTDB will also be set.
    if voltdb_jar is None:
        globs = list(voltdb_search_globs)
        globs.sort()
        utility.abort('Failed to find the VoltDB jar file.',
                        ('You may need to perform a build.',
                         'Searched the following:', globs))

    if not voltdb_lib:
        globs = list(lib_search_globs)
        globs.sort()
        utility.abort('Failed to find the VoltDB library directory.',
                        ('You may need to perform a build.',
                         'Searched the following:', globs))

    # LOG4J configuration
    if 'LOG4J_CONFIG_PATH' not in os.environ:
        for chk_dir in ('$VOLTDB_LIB/../src/frontend', '$VOLTDB_VOLTDB'):
            path = os.path.join(os.path.realpath(os.path.expandvars(chk_dir)), 'log4j.xml')
            if os.path.exists(path):
                os.environ['LOG4J_CONFIG_PATH'] = path
                utility.debug('LOG4J_CONFIG_PATH=>%s' % os.environ['LOG4J_CONFIG_PATH'])
                break
        else:
            utility.abort('Could not find log4j configuration file or LOG4J_CONFIG_PATH variable.')

    for var in ('VOLTDB_LIB', 'VOLTDB_VOLTDB', 'LOG4J_CONFIG_PATH'):
        utility.verbose_info('Environment: %s=%s' % (var, os.environ[var]))

    # Classpath is the voltdb jar and all the jars in VOLTDB_LIB, and if present,
    # any user supplied jars under VOLTDB/lib/extension
    global classpath
    classpath = [voltdb_jar]
    for path in glob.glob(os.path.join(voltdb_lib, '*.jar')):
        classpath.append(path)
    for path in glob.glob(os.path.join(os.environ['VOLTDB_LIB'], 'extension', '*.jar')):
        classpath.append(path)
    utility.verbose_info('Classpath: %s' % ':'.join(classpath))
