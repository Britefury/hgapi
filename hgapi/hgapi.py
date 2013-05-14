# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals, with_statement
import sys

from subprocess import Popen, STDOUT, PIPE
from datetime import datetime

try:
    from ConfigParser import ConfigParser, NoOptionError
except: #python 3
    from configparser import ConfigParser, NoOptionError
import re
import os
import shutil

try:
    from urllib import unquote
except: #python 3
    from urllib.parse import unquote

try:
    import json #for reading logs
except:
    import simplejson as json





from revision import Revision
from status import Status, ResolveState




PLATFORM_WINDOWS = 'windows'
PLATFORM_LINUX = 'linux'
PLATFORM_MAC = 'mac'


def _get_platform():
    os_name = sys.registry['os.name']
    if os_name.startswith( 'Windows' ):
        return PLATFORM_WINDOWS
    elif os_name.startswith( 'Linux' ):
        return PLATFORM_LINUX
    elif os_name.startswith( 'Mac' ):
        return PLATFORM_MAC
    else:
        raise ValueError, 'Unrecognized os.name \'{0}\''.format(os_name)




def __platform_ssh_cmd(username, ssh_key_path):
    platform = _get_platform()
    if platform == PLATFORM_WINDOWS:
        return 'TortoisePLink.exe -ssh -l {0} -i "{1}"'.format(username, ssh_key_path)
    elif platform == PLATFORM_LINUX:
        return 'ssh -l {0} -i "{1}"'.format(username, ssh_key_path)
    elif platform == PLATFORM_MAC:
        return 'ssh -l {0} -i "{1}"'.format(username, ssh_key_path)
    else:
        raise ValueError, 'Unreckognized platform \'{0}\''.format(platform)



__hg_path = 'hg'


def get_hg_path():
    return __hg_path


def set_hg_path(p):
    global __hg_path
    __hg_path = p



def _ssh_cmd_config_option(username, ssh_key_path):
    if username is not None  and  ssh_key_path is not None:
        cmd = __platform_ssh_cmd(username, ssh_key_path)
        return ['--config', 'ui.ssh={0}'.format(cmd)]
    else:
        return []


MERGETOOL_INTERNAL_DUMP = 'internal:dump'
MERGETOOL_INTERNAL_FAIL = 'internal:fail'
MERGETOOL_INTERNAL_LOCAL = 'internal:local'
MERGETOOL_INTERNAL_MERGE = 'internal:merge'
MERGETOOL_INTERNAL_OTHER = 'internal:other'
MERGETOOL_INTERNAL_PROMPT = 'internal:prompt'


class HGBaseError (Exception):
    pass

class HGError (HGBaseError):
    pass

class HGCannotLaunchError (HGBaseError):
    pass

class HGExtensionDisabledError (HGBaseError):
    pass

class HGPushNothingToPushError (HGBaseError):
    pass

class HGRemoveWarning (HGBaseError):
    pass

class HGMoveError (HGBaseError):
    pass

class HGCopyError (HGBaseError):
    pass

class HGUnresolvedFiles (HGBaseError):
    pass

class HGHeadsNoHeads (HGBaseError):
    pass

class HGResolveFailed (HGBaseError):
    pass

class HGCommitNoChanges (HGBaseError):
    pass

class HGRebaseNothingToRebase (HGBaseError):
    pass





class _ReturnCodeHandler (object):
    def __init__(self):
        self.__exc_type_map = {}


    def map_returncode_to_exception(self, returncode, exc_type):
        x = _ReturnCodeHandler()
        x.__exc_type_map.update(self.__exc_type_map)
        x.__exc_type_map[returncode] = exc_type
        return x


    def _handle_return_code(self, cmd, err, out, returncode):
        exc_type = self.__exc_type_map.get(returncode, HGError)
        raise exc_type("Error running %s:\n\tErr: %s\n\tOut: %s\n\tExit: %s"
                      % (' '.join(cmd),err,out,returncode))


_default_return_code_handler = _ReturnCodeHandler()





def _hg_cmd(username, ssh_key_path, *args):
    """Run a hg command in path and return the result.
    Throws on error."""
    cmd = [get_hg_path(), "--encoding", "UTF-8"] + _ssh_cmd_config_option(username, ssh_key_path) + list(args)
    proc = Popen(cmd, stdout=PIPE, stderr=PIPE)

    out, err = [x.decode("utf-8") for x in  proc.communicate()]

    if proc.returncode:
        _default_return_code_handler._handle_return_code(cmd, err, out, proc.returncode)
    return out


class Repo(object):
    __user_cfg_mod_date = None

    """A representation of a Mercurial repository"""
    def __init__(self, path, user=None, ssh_key_path=None, on_filesystem_modified=None):
        """Create a Repo object from the repository at path"""
        # Call hg_version() to check that it is installed and that it works
        hg_version()
        self.path = path
        self.__cfg_date = None
        self.__cfg = None
        self.user = user
        self.ssh_key_path = ssh_key_path
        self.__on_filesystem_modified = on_filesystem_modified
        # Call hg_status to check that the repo is valid
        self.hg_status()
        self.__extensions = set()
        self.__refresh_extensions()

        self.__revisions_by_index = []

 
    def __getitem__(self, rev=slice(0, 'tip')):
        """Get a Revision object for the revision identifed by rev
           rev can be a range (6c31a9f7be7ac58686f0610dd3c4ba375db2472c:tip)
           a single changeset id
           or it can be left blank to indicate the entire history
        """
        if isinstance(rev, slice):
            return self.revisions(":".join([str(x)for x in (rev.start, rev.stop)]))
        return self.revision(rev)

    def hg_command(self, return_code_handler, *args):
        """Run a hg command in path and return the result.
        Throws on error."""
        assert return_code_handler is None  or  isinstance(return_code_handler, _ReturnCodeHandler)
        cmd = [get_hg_path(), "--cwd", self.path, "--encoding", "UTF-8"] + list(args)
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)

        out, err = [x.decode("utf-8") for x in  proc.communicate()]

        if proc.returncode:
            if return_code_handler is not None:
                return_code_handler._handle_return_code(cmd, err, out, proc.returncode)
            else:
                _default_return_code_handler._handle_return_code(cmd, err, out, proc.returncode)
            raise HGError("Error running %s:\n\tErr: %s\n\tOut: %s\n\tExit: %s"
                    % (' '.join(cmd),err,out,proc.returncode))
        return out

    def hg_remote_command(self, return_code_handler, *args):
        """Run a hg command in path and return the result.
        Throws on error.
        Adds SSH key path"""
        return self.hg_command(return_code_handler, *(_ssh_cmd_config_option(self.user, self.ssh_key_path) + list(args)))





    def read_repo_config(self):
        """Read the repo configuration and return a ConfigParser object"""
        config = ConfigParser()
        config_path = os.path.join(self.path, '.hg', 'hgrc')
        if os.path.exists(config_path):
            config.read(config_path)
        return config

    def write_repo_config(self, config):
        """Write the repo configuration in the form of a ConfigParser object"""
        with open(os.path.join(self.path, '.hg', 'hgrc'), 'w') as f:
            config.write(f)
        self.__cfg = None

    def is_extension_enabled(self, extension_name):
        """Determine if a named HG extension is enabled"""
        self.__refresh_extensions()
        return extension_name in self.__extensions

    def enable_extension(self, extension_name):
        """Enable a named HG extension"""
        config = self.read_repo_config()
        if not config.has_section('extensions'):
            config.add_section('extensions')
        if not config.has_option('extensions', extension_name):
            config.set('extensions', extension_name, '')
            self.write_repo_config(config)


    @staticmethod
    def read_user_config():
        """Read the user HG configuration, returns a ConfigParser object"""
        config = ConfigParser()
        config_path = os.path.expanduser(os.path.join('~', '.hgrc'))
        if os.path.exists(config_path):
            config.read(config_path)
        return config

    @staticmethod
    def write_user_config(config):
        """Write the user HG configuration, in the form of a ConfigParser"""
        with open(os.path.expanduser(os.path.join('~', '.hgrc')), 'w') as f:
            config.write(f)
        Repo.__user_cfg_mod_date = datetime.now()


    def __refresh_extensions(self):
        cfg = self.__refresh_config()
        self.__extensions = set(cfg.get('extensions', []))


    def hg_id(self):
        """Get the output of the hg id command"""
        res = self.hg_command(None, "id", "-i")
        return res.strip("\n +")
        
    def hg_rev(self):
        """Get the revision number of the current revision"""
        res = self.hg_command(None, "id", "-n")
        str_rev = res.strip("\n +")
        return int(str_rev)

    def hg_node(self, rev_id=None):
        """Get the full node id of a revision

        rev_id - a string identifying the revision. If None, will use the current working directory
        """
        if rev_id is None:
            rev_id = self.hg_id()
        res = self.hg_command(None, "log", "-r", rev_id, "--template", "{node}")
        return res.strip()




    def hg_log(self, rev_identifier=None, limit=None, template=None, filename=None, **kwargs):
        """Get repositiory log."""
        cmds = ["log"]
        if rev_identifier: cmds += ['-r', str(rev_identifier)]
        if limit: cmds += ['-l', str(limit)]
        if template: cmds += ['--template', str(template)]
        if kwargs:
            for key in kwargs:
                cmds += [key, kwargs[key]]
        if filename:
            cmds.append(filename)
        return self.hg_command(None, *cmds)



    def hg_status(self):
        """Get repository status.
        Returns a dict containing a *change char* -> *file list* mapping, where
        change char is in::

         A, M, R, !, ?

        Example - added one.txt, modified a_folder/two.txt and three.txt::

         {'A': ['one.txt'], 'M': ['a_folder/two.txt', 'three.txt'],
         '!': [], '?': [], 'R': []}

        If empty is set to non-False value, don't add empty lists
        """
        cmds = ['status']
        out = self.hg_command(None, *cmds).strip()
        #default empty set
        status = Status()
        if not out: return status
        lines = out.split("\n")
        status_split = re.compile("^(.) (.*)$")

        for change, path in [status_split.match(x).groups() for x in lines]:
            getattr(status, self._status_codes[change]).add(path)
        return status

    _status_codes = {'A': 'added', 'M': 'modified', 'R': 'removed', '!': 'missing', '?': 'untracked'}
    rev_log_tpl = '\{"node":"{node}","rev":"{rev}","author":"{author|urlescape}","branch":"{branches}","parents":"{parents}","date":"{date|isodate}","tags":"{tags}","desc":"{desc|urlescape}\"}\n'



    @staticmethod
    def __revision_from_json(json_rev):
        """Create a Revision object from a JSON representation"""
        j = json.loads(json_rev)
        j = {key : unquote(value)   for key, value in j.items()}
        rev = int(j['rev'])
        branch = j['branch']
        branch = branch   if branch   else 'default'
        jparents = j['parents']
        if not jparents:
            parents = [rev-1]
        else:
            parents = [int(p.split(':')[0])   for p in jparents.split()]
        return Revision(j['node'], rev, j['author'], branch, parents, j['date'], j['tags'], j['desc'])



    @staticmethod
    def __revision_from_log(log):
        log = log.strip()
        if len(log) > 0:
            return Repo.__revision_from_json(log)
        else:
            return None

    @staticmethod
    def __revisions_from_log(log):
        lines = log.split('\n')[:-1]
        lines = [line.strip()   for line in lines]
        return [Repo.__revision_from_json(line)   for line in lines   if len(line) > 0]




    def revision(self, rev_identifier):
        """Get the identified revision as a Revision object"""
        out = self.hg_log(rev_identifier=str(rev_identifier), template=self.rev_log_tpl)
        return Repo.__revision_from_log(out)

    def revisions(self, rev_identifier):
        """Returns a list of Revision objects for the given identifier"""
        out = self.hg_log(rev_identifier=str(rev_identifier), template=self.rev_log_tpl)
        return Repo.__revisions_from_log(out)


    def revisions_for(self, filename, rev_identifier=None):
        """Returns a list of Revision objects for the given identifier"""
        out = self.hg_log(rev_identifier=str(rev_identifier)   if rev_identifier is not None   else None, template=self.rev_log_tpl, filename=filename)
        return Repo.__revisions_from_log(out)


    def hg_paths(self):
        """Returns aliases for remote repositories"""
        out = self.hg_command(None, 'paths')
        lines = [l.strip()   for l in out.split('\n')]
        pairs = [l.split('=')   for l in lines   if l != '']
        return {a.strip() : b.strip()   for a, b in pairs}

    def hg_path(self, name):
        """Returns the alias for the given name"""
        out = self.hg_command(None, 'paths', name)
        out = out.strip()
        return out   if out != ''   else None





    _heads_handler = _ReturnCodeHandler().map_returncode_to_exception(1, HGHeadsNoHeads)

    def hg_heads(self):
        """Gets a list with the node id's of all open heads"""
        res = self.hg_command(self._heads_handler, "heads","--template", "{node}\n")
        return [head for head in res.split("\n") if head]




    def hg_add(self, filepath):
        """Add a file to the repo"""
        self.hg_command(None, "add", filepath)

    _remove_handler = _ReturnCodeHandler().map_returncode_to_exception(1, HGRemoveWarning)

    def hg_remove(self, filepath):
        """Remove a file from the repo"""
        self.hg_command(self._remove_handler, "remove", filepath)

    _move_handler = _ReturnCodeHandler().map_returncode_to_exception(1, HGMoveError)

    def hg_move(self, srcpath, destpath):
        """Move/rename a file in the repo"""
        self.hg_command(self._move_handler, "move", srcpath, destpath)

    _copy_handler = _ReturnCodeHandler().map_returncode_to_exception(1, HGCopyError)

    def hg_copy(self, srcpath, destpath):
        """Copy a file in the repo"""
        self.hg_command(self._copy_handler, "copy", srcpath, destpath)





    _commit_handler = _ReturnCodeHandler().map_returncode_to_exception(1, HGCommitNoChanges)

    def hg_commit(self, message, user=None, files=[], close_branch=False):
        """Commit changes to the repository."""
        userspec = "-u" + user if user else "-u" + self.user if self.user else ""
        close = "--close-branch" if close_branch else ""
        args = [close, userspec] + files
        # don't send a "" arg for userspec or close, which HG will
        # consider the files arg, committing all files instead of what
        # was passed in files kwarg
        args = [arg for arg in args if arg]
        self.hg_command(self._commit_handler, "commit", "-m", message, *args)




    def hg_revert(self, all=False, *files):
        """Revert repository"""

        if all:
            cmd = ["revert", "--all"]
        else:
            cmd = ["revert"] + list(files)
        self.hg_command(None, *cmd)
        self._notify_filesystem_modified()







    _unresolved_handler = _ReturnCodeHandler().map_returncode_to_exception(1, HGUnresolvedFiles)

    def hg_update(self, reference, clean=False):
        """Update to the revision indetified by reference"""
        cmd = ["update"]
        if reference is not None:
            cmd.append(str(reference))
        if clean: cmd.append("--clean")
        try:
            self.hg_command(self._unresolved_handler, *cmd)
        finally:
            self._notify_filesystem_modified()


    def hg_merge(self, reference=None, tool=None):
        """Merge reference to current"""
        cmd = ['merge']
        if reference is not None:
            cmd.append('-r')
            cmd.append(reference)
        if tool is not None:
            cmd.append('--tool')
            cmd.append(tool)
        try:
            self.hg_command(self._unresolved_handler, *cmd)
        finally:
            self._notify_filesystem_modified()

    _resolve_handler = _ReturnCodeHandler().map_returncode_to_exception(1, HGResolveFailed)

    def hg_resolve_remerge(self, tool=None, files=None):
        cmd = ['resolve']
        if tool is not None:
            cmd.append('--tool')
            cmd.append(tool)
        if files is None:
            cmd.append('--all')
        else:
            cmd.extend(files)
        try:
            self.hg_command(self._resolve_handler, *cmd)
        finally:
            self._notify_filesystem_modified()

    def hg_resolve_mark_as_resolved(self, files=None):
        cmd = ['resolve', '-m']
        if files is not None:
            cmd.extend(files)
        self.hg_command(self._resolve_handler, *cmd)

    def hg_resolve_mark_as_unresolved(self, files=None):
        cmd = ['resolve', '-u']
        if files is not None:
            cmd.extend(files)
        self.hg_command(self._resolve_handler, *cmd)

    def hg_resolve_list(self):
        cmd = ['resolve', '-l']
        resolve_result = self.hg_command(self._resolve_handler, *cmd)
        unresolved_list = resolve_result.strip().split("\n")
        # Create the resolve state
        state = ResolveState()
        # Fill it in
        for u in unresolved_list:
            u = u.strip()
            if u != '':
                code, name = u.split(' ')
                if code == 'R':
                    state.resolved.add(name)
                elif code == 'U':
                    state.unresolved.add(name)
                else:
                    raise ValueError, 'Unknown resolve code \'{0}\''.format(code)
        return state


    def hg_merge_custom(self, reference=None):
        """Merge reference to current, with custom conflict resolution

        Returns a CustomMergeState that describes files that are in an unresolved state, allowing the application
        to handle them.

        Uses the HG 'internal:dump' merging tool, causing the base and derived versions of the file to be written,
        where the application can access them.
        """
        try:
            self.hg_merge(reference, MERGETOOL_INTERNAL_DUMP)
        except HGUnresolvedFiles:
            # We have unresolved files
            pass
        finally:
            self._notify_filesystem_modified()
        return self.hg_resolve_list()


    def hg_resolve_custom_take_local(self, file):
        self.__hg_resolve_custom_take(file, '.local')


    def hg_resolve_custom_take_other(self, file):
        self.__hg_resolve_custom_take(file, '.other')



    def __hg_resolve_custom_take(self, file, suffix):
        path = os.path.join(self.path, file)
        merge_path = path + suffix
        if not os.path.exists(path):
            raise IOError, 'File \'{0}\' does not exist'.format(path)
        if not os.path.exists(merge_path):
            raise IOError, 'Merge file \'{0}\' does not exist'.format(merge_path)
        shutil.copyfile(path, merge_path)
        self.hg_resolve_mark_as_resolved([file])




    def remove_merge_files(self, files):
        """Remove files resulting from merging

        files - a file name or a collection of filenames

        For each file in the input list, the existence of .base, .local, .other and .orig files it tested.
        If they exist, they are deleted
        """
        if isinstance(files, str)  or  isinstance(files, unicode):
            files = [files]

        removed = False

        for file in files:
            merge_file_paths = [os.path.join(self.path, file + suffix)   for suffix in ['.base', '.local', '.other', '.orig']]
            for m in merge_file_paths:
                if os.path.exists(m):
                    os.remove(m)
                    removed = True

        if removed:
            self._notify_filesystem_modified()




    def hg_pull(self):
        return self.hg_remote_command(self._unresolved_handler, 'pull')


    _push_handler = _ReturnCodeHandler().map_returncode_to_exception(1, HGPushNothingToPushError)

    def hg_push(self, force=False):
        cmd = ['push']
        if force:
            cmd.append('--force')
        return self.hg_remote_command(self._push_handler, *cmd)



    def get_branches(self, active_only=False, show_closed=False):
        """ Returns a list of branches from the repo, including versions """
        cmd = ['branches']
        if active_only:
            cmd.append('--active')
        if show_closed:
            cmd.append('--closed')
        branches = self.hg_command(None, *cmd)
        branch_list = branches.strip().split("\n")
        values = []
        for branch in branch_list:
            b = branch.partition(" ")
            if not b:
                continue
            name = b[0].strip()
            version = b[-1].strip()
            values.append({'name':name, 'version':version})
        return values

    def get_branch_names(self, active_only=False, show_closed=False):
        return [branch['name']   for branch in self.get_branches(active_only=active_only, show_closed=show_closed)]




    def hg_branch(self, branch_name=None):
        """ Creates a branch of branch_name isn't None
            If not, returns the current branch name.
        """
        args = []
        if branch_name:
            args.append(branch_name)
        branch = self.hg_command(None, "branch", *args)
        return branch.strip()

    _rebase_handler = _ReturnCodeHandler().map_returncode_to_exception(1, HGRebaseNothingToRebase)





    def hg_rebase(self, source, destination):
        if not self.is_extension_enabled('rebase'):
            raise HGExtensionDisabledError, 'rebase extension is disabled'
        cmd = ['rebase', '--source', str(source), '--dest', str(destination)]
        return self.hg_command(self._rebase_handler, *cmd)

    def enable_rebase(self):
        self.enable_extension('rebase')




    def read_config(self):
        """Read the configuration as seen with 'hg showconfig'
        Is called by __init__ - only needs to be called explicitly
        to reflect changes made since instantiation"""

        # Not technically a remote command, but use hg_remote_command so that the SSH key path config option is present
        res = self.hg_remote_command(None, "showconfig")
        cfg = {}
        for row in res.split("\n"):
            section, ign, value = row.partition("=")
            main, ign, sub = section.partition(".")
            sect_cfg = cfg.setdefault(main, {})
            sect_cfg[sub] = value.strip()
        self.__cfg = cfg
        self.__cfg_date = datetime.now()
        return cfg


    def __refresh_config(self):
        if self.__cfg is None  or  \
                (self.__cfg_date is not None and  \
                Repo.__user_cfg_mod_date is not None and  \
                self.__cfg_date < Repo.__user_cfg_mod_date):
            self.read_config()
        return self.__cfg

    def config(self, section, key):
        """Return the value of a configuration variable"""
        cfg = self.__refresh_config()
        return cfg.get(section, {}).get(key, None)
    
    def configbool(self, section, key):
        """Return a config value as a boolean value.
        Empty values, the string 'false' (any capitalization),
        and '0' are considered False, anything else True"""
        cfg = self.__refresh_config()
        value = cfg.get(section, {}).get(key, None)
        if not value: 
            return False
        if (value == "0" 
            or value.upper() == "FALSE"
            or value.upper() == "None"): 
            return False
        return True

    def configlist(self, section, key):
        """Return a config value as a list; will try to create a list
        delimited by commas, or whitespace if no commas are present"""
        cfg = self.__refresh_config()
        value = cfg.get(section, {}).get(key, None)
        if not value: 
            return []
        if value.count(","):
            return value.split(",")
        else:
            return value.split()


    def _notify_filesystem_modified(self):
        if self.__on_filesystem_modified is not None:
            self.__on_filesystem_modified()


    @staticmethod
    def hg_init(path, user=None, ssh_key_path=None, on_filesystem_modified=None):
        """Initialize a new repo"""
        # Call hg_version() to check that it is installed and that it works
        hg_version()
        _hg_cmd(user, None, 'init', path)
        repo = Repo(path, user, ssh_key_path=ssh_key_path, on_filesystem_modified=on_filesystem_modified)
        return repo

    @staticmethod
    def hg_clone(path, remote_uri, user=None, ssh_key_path=None, on_filesystem_modified=None, ok_if_local_dir_exists=False):
        """Clone an existing repo"""
        # Call hg_version() to check that it is installed and that it works
        hg_version()
        if os.path.exists(path):
            if os.path.isdir(path):
                if not ok_if_local_dir_exists:
                    raise HGError, 'Local directory \'{0}\' already exists'.format(path)
            else:
                raise HGError, 'Cannot clone into \'{0}\'; it is not a directory'.format(path)
        else:
            os.makedirs(path)
        _hg_cmd(user, ssh_key_path, 'clone', remote_uri, path)
        repo = Repo(path, user, ssh_key_path=ssh_key_path, on_filesystem_modified=on_filesystem_modified)
        return repo



def hg_version():
    """Return version number of mercurial"""
    try:
        proc = Popen([get_hg_path(), "version"], stdout=PIPE, stderr=PIPE)
    except:
        raise HGCannotLaunchError, 'Cannot launch hg executable'
    out, err = [x.decode("utf-8") for x in  proc.communicate()]
    if proc.returncode:
        raise HGCannotLaunchError, 'Cannot get hg version'
    match = re.search('\s(([\w\.\-]+?)(\+[0-9]+)?)\)$', out.split("\n")[0])
    return match.group(1)





def hg_check():
    try:
        hg_version()
    except HGCannotLaunchError:
        return False
    else:
        return True



