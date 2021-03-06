from __future__ import with_statement
import unittest, doctest
import os, shutil, os.path
import tempfile
import zipfile
import hgapi
import tempfile
import tarfile

class TestHgAPI(unittest.TestCase):
    """Tests for hgapi.py
    Uses and wipes subfolder named 'test'
    Tests are dependant on each other; named test_<number>_name for sorting
    """
    _user = 'testuser'

    @classmethod
    def setUpClass(cls):
        #Patch Python 3
        if hasattr(cls, "assertEqual"):
            setattr(cls, "assertEquals", cls.assertEqual)
            setattr(cls, "assertNotEquals", cls.assertNotEqual)

        cls._test_dir_path = tempfile.mkdtemp(prefix='testhgapi_repo')
        cls._clone1_path = tempfile.mkdtemp(prefix='testhgapi_clone1')
        cls._clone2_path = tempfile.mkdtemp(prefix='testhgapi_clone2')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._test_dir_path)
        if os.path.exists(cls._clone1_path):
            shutil.rmtree(cls._clone1_path)
        if os.path.exists(cls._clone2_path):
            shutil.rmtree(cls._clone2_path)



    def _file_contents(self, path):
        with open(path, 'r') as f:
            return f.read()


    def _test_file(self, filename):
        return os.path.join(self._test_dir_path, filename)

    def _clone1_file(self, filename):
        return os.path.join(self._clone1_path, filename)

    def _clone2_file(self, filename):
        return os.path.join(self._clone2_path, filename)



    def test_000_Init(self):
        TestHgAPI.repo = hgapi.Repo.hg_init(self._test_dir_path, user=self._user)
        self.assertTrue(os.path.exists(self._test_file(".hg")))

    def test_010_Identity(self):
        rev = self.repo.hg_rev()
        hgid = self.repo.hg_id()
        self.assertEquals(-1, rev)
        self.assertEquals("000000000000", hgid)
        self.assertRaises(hgapi.HGHeadsNoHeads, lambda: self.repo.hg_heads())

    def test_020_Add(self):
        with open(self._test_file('file.txt'), "w") as out:
            out.write("stuff\n")
        self.repo.hg_add("file.txt")
        
    def test_030_Commit(self):
        #Commit and check that we're on a real revision
        self.repo.hg_commit("adding", user="test")
        rev  = self.repo.hg_rev()
        hgid = self.repo.hg_id()
        self.assertEquals(rev, 0)
        self.assertNotEquals(hgid, "000000000000")

        #write some more to file
        with open(self._test_file('file.txt'), "w+") as out:
            out.write("more stuff\n")

        #Commit and check that changes have been made
        self.repo.hg_commit("modifying", user="test")
        rev2  = self.repo.hg_rev()
        hgid2 = self.repo.hg_id()
        self.assertNotEquals(rev, rev2)
        self.assertNotEquals(hgid, hgid2)

        # Try to commit with no changes
        self.assertRaises(hgapi.HGCommitNoChanges, lambda: self.repo.hg_commit('nothing', user='test'))

    def test_040_Log(self):
        rev = self.repo[0]
        self.assertEquals(rev.desc, "adding")
        self.assertEquals(rev.author, "test")
        self.assertEquals(rev.branch, "default")
        self.assertEquals(rev.parents, [-1])

    def test_050_Update(self):
        node = self.repo.hg_id()
        self.repo.hg_update(1)
        self.assertEquals(self.repo.hg_rev(), 1)
        self.repo.hg_update("tip")
        self.assertEquals(self.repo.hg_id(), node)


    def test_060_Heads(self):
        node = self.repo.hg_node()

        self.repo.hg_update(0)
        with open(self._test_file('file.txt'), "w+") as out:
            out.write("even more stuff\n")

        #creates new head
        self.repo.hg_commit("modifying", user="test")

        heads = self.repo.hg_heads()
        self.assertEquals(len(heads), 2)
        self.assertTrue(node in heads)
        self.assertTrue(self.repo.hg_node() in heads)

        #Close head again
        self.repo.hg_commit("Closing branch", close_branch=True)
        self.repo.hg_update(node)

        #Check that there's only one head remaining
        heads = self.repo.hg_heads()
        self.assertEquals(len(heads), 1)
        self.assertTrue(node in heads)

    def test_070_Config(self):
        with open(self._test_file('.hg/hgrc'), "w") as hgrc:
            hgrc.write("[test]\n" +
                       "stuff.otherstuff = tsosvalue\n" +
                       "stuff.debug = True\n" +
                       "stuff.verbose = false\n" +
                       "stuff.list = one two three\n" +
                       "[ui]\n" +
                       "username = testsson")
        #re-read config
        self.repo.read_config()     
        self.assertEquals(self.repo.config('test', 'stuff.otherstuff'),
                          "tsosvalue")
        self.assertEquals(self.repo.config('ui', 'username'),
                          "testsson")


    def test_071_ConfigBool(self):
        self.assertTrue(self.repo.configbool('test', 'stuff.debug'))
        self.assertFalse(self.repo.configbool('test', 'stuff.verbose'))
        
    def test_072_ConfigList(self):
        self.assertTrue(self.repo.configlist('test', 'stuff.list'),
                        ["one", "two", "three"])

    def test_080_LogBreakage(self):
        """Some log messages/users could possibly break 
        the revision parsing"""
        #write some more to file
        with open(self._test_file('file.txt'), "w+") as out:
            out.write("stuff and, more stuff\n")

        #Commit and check that changes have been made
        self.repo.hg_commit("}", user="},desc=\"test")
        self.assertEquals(self.repo["tip"].desc, "}")
        self.assertEquals(self.repo["tip"].author, "},desc=\"test")


    def test_090_Move(self):
        with open(self._test_file('file_to_move.txt'), "w") as out:
            out.write("Text that will be moved quite soon....")
        self.repo.hg_add("file_to_move.txt")
        self.repo.hg_commit(message="Added a file that is soon to be moved")
        self.repo.hg_move("file_to_move.txt", "file_moved.txt")
        self.repo.hg_commit(message="Moved the file")
        self.assertFalse(os.path.exists(self._test_file('file_to_move.txt')))
        self.assertTrue(os.path.exists(self._test_file('file_moved.txt')))

        f = open(self._test_file('file_moved.txt'))
        contents = f.read()
        f.close()
        self.assertEqual(contents, "Text that will be moved quite soon....")


    def test_091_Copy(self):
        self.repo.hg_copy("file_moved.txt", "copy_of_file_moved.txt")
        self.repo.hg_commit(message="copied the file")
        self.assertTrue(os.path.exists(self._test_file('file_moved.txt')))
        self.assertTrue(os.path.exists(self._test_file('copy_of_file_moved.txt')))

        f = open(self._test_file('copy_of_file_moved.txt'))
        contents = f.read()
        f.close()
        self.assertEqual(contents, "Text that will be moved quite soon....")

        TestHgAPI.__rev_after_test_copy = self.repo.hg_rev()


    def test_100_ModifiedStatus(self):
        #write some more to file
        with open(self._test_file('file.txt'), "a") as out:
            out.write("stuff stuff stuff\n")
        status = self.repo.hg_status()
        self.assertEquals(status, hgapi.Status(modified=['file.txt']))

    def test_110_CleanStatus(self):
        #commit file created in 090
        self.repo.hg_commit("Comitting changes", user="test")
        #Assert status is empty
        self.assertEquals(self.repo.hg_status(), hgapi.Status())

    def test_120_UntrackedStatus(self):
        #Create a new file
        with open(self._test_file('file2.txt'), "w") as out:
            out.write("stuff stuff stuff")
        status = self.repo.hg_status()
        self.assertEquals(status, hgapi.Status(untracked=['file2.txt']))

    def test_130_AddedStatus(self):
        #Add file created in 110
        self.repo.hg_add("file2.txt")
        status = self.repo.hg_status()
        self.assertEquals(status, hgapi.Status(added=['file2.txt']))

    def test_140_MissingStatus(self):
        #Commit file created in 120
        self.repo.hg_commit("Added file")
        import os
        os.unlink(self._test_file('file2.txt'))
        status = self.repo.hg_status()
        self.assertEquals(status, hgapi.Status(missing=['file2.txt']))

    def test_150_RemovedStatus(self):
        #Remove file from repo
        self.repo.hg_remove("file2.txt")
        status = self.repo.hg_status()
        self.assertEquals(status, hgapi.Status(removed=['file2.txt']))

    def test_160_EmptyStatus(self):
        self.repo.hg_revert(all=True)
        status = self.repo.hg_status()
        self.assertEquals(status, hgapi.Status())


    def test_170_Remove_modified(self):
        #write some more to file
        with open(self._test_file('file.txt'), "a") as out:
            out.write("stuff stuff stuff\n")
        self.assertRaises(hgapi.HGRemoveWarning, lambda: self.repo.hg_remove("file.txt"))
        # Revert the changes
        self.repo.hg_revert("file.txt")
        os.remove(self._test_file('file.txt.orig'))


    def test_180_Revert_modified(self):
        # Get the contents of file.txt
        with open(self._test_file('file.txt'), 'r') as f:
            original_contents = f.read()

        # Replace it's contents
        with open(self._test_file('file.txt'), "w") as out:
            out.write("Only one line of content\n")


        # Get the status
        status = self.repo.hg_status()
        self.assertEquals(status, hgapi.Status(modified=['file.txt']))

        # Get the modified contents and check
        with open(self._test_file('file.txt'), 'r') as f:
            modified_contents = f.read()
        self.assertEqual(modified_contents, "Only one line of content\n")

        # Revert and check again
        self.repo.hg_revert(all=True)

        # Should have created file.txt.orig
        self.assertTrue(os.path.exists(self._test_file('file.txt.orig')))

        # Check the contents of file.txt
        with open(self._test_file('file.txt'), 'r') as f:
            reverted_contents = f.read()
        self.assertEqual(reverted_contents, original_contents)

        # Remove file.txt.orig
        os.unlink(self._test_file('file.txt.orig'))


    def test_181_Revert_added(self):
        # Add a new file
        with open(self._test_file('file_added.txt'), "w") as out:
            out.write("Added content\n")

        self.repo.hg_add('file_added.txt')


        # Get the status
        status = self.repo.hg_status()
        self.assertEquals(status, hgapi.Status(added=['file_added.txt']))

        with open(self._test_file('file_added.txt'), 'r') as f:
            new_contents = f.read()
        self.assertEqual(new_contents, "Added content\n")

        # Revert and check again
        self.repo.hg_revert(all=True)

        # file_added.txt should still exist
        self.assertTrue(os.path.exists(self._test_file('file_added.txt')))

        os.unlink(self._test_file('file_added.txt'))


    def test_182_Revert_removed(self):
        # Remove file.txt
        self.repo.hg_remove("file.txt")

        # file.txt should be gone
        self.assertFalse(os.path.exists(self._test_file('file.txt')))

        # Check the status
        status = self.repo.hg_status()
        self.assertEquals(status, hgapi.Status(removed=['file.txt']))

        # Revert and check again
        self.repo.hg_revert(all=True)

        # file.txt should be back
        self.assertTrue(os.path.exists(self._test_file('file.txt')))

        # Check the status
        status = self.repo.hg_status()
        self.assertEquals(status, hgapi.Status())



    def test_190_ForkAndMerge(self):
        #Store this version
        node = self.repo.hg_node()

        self.repo.hg_update(4, clean=True)
        with open(self._test_file('file3.txt'), "w") as out:
            out.write("this is more stuff")

        #creates new head
        self.repo.hg_add("file3.txt")
        self.repo.hg_commit("adding head", user="test")

        heads = self.repo.hg_heads()
        self.assertEquals(len(heads), 2)
        self.assertTrue(node in heads)
        self.assertTrue(self.repo.hg_node() in heads)

        #merge the changes
        self.repo.hg_merge(node)
        self.repo.hg_commit("merge")
        
        #Check that there's only one head remaining
        heads = self.repo.hg_heads()
        self.assertEquals(len(heads), 1)

    def test_200_CommitFiles(self):
        with open(self._test_file('file2.txt'), "w") as out:
                    out.write("newstuff")        	
        with open(self._test_file('file3.txt'), "w") as out:
            out.write("this is even more stuff")
        self.repo.hg_commit("only committing file2.txt", user="test", files=["file2.txt"])
        self.assertTrue("file3.txt" in self.repo.hg_status().modified)
        
    def test_210_Indexing(self):
        with open(self._test_file('file2.txt'), "a+") as out:
            out.write("newstuff")
        self.repo.hg_commit("indexing", user="test", files=["file2.txt"])
        #Compare tip and current revision number
        self.assertEquals(self.repo['tip'], self.repo[self.repo.hg_rev()])
        self.assertEquals(self.repo['tip'].desc, "indexing")
        
    def test_220_Slicing(self):
        with open(self._test_file('file2.txt'), "a+") as out:
            out.write("newstuff")
        self.repo.hg_commit("indexing", user="test", files=["file2.txt"])
        
        all_revs = self.repo[0:'tip']
        self.assertEquals(len(all_revs), 15)
        self.assertEquals(all_revs[-1].desc, all_revs[-2].desc)
        self.assertNotEquals(all_revs[-2].desc, all_revs[-3].desc)
        
    def test_230_Branches(self):
        # make sure there is only one branch and it is default
        self.assertEquals(self.repo.hg_branch(), "default")
        branches = self.repo.get_branches()
        self.assertEquals(len(branches), 1)
        branch_names = self.repo.get_branch_names()
        self.assertEquals(len(branch_names), 1)
        self.assertEquals(branch_names[0], "default")

        # create a new branch, should still be default in branches until we commit
        # but branch should return the new branch
        self.assertEquals(self.repo.hg_branch('test_branch'),
            "marked working directory as branch test_branch\n(branches are permanent and global, did you want a bookmark?)")
        self.assertEquals(self.repo.hg_branch(), "test_branch")
        branches = self.repo.get_branches()
        self.assertEquals(len(branches), 1)
        branch_names = self.repo.get_branch_names()
        self.assertEquals(len(branch_names), 1)
        self.assertEquals(branch_names[0], "default")

        # now commit. branch and branches should change to test_branch
        self.repo.hg_commit("commit test_branch")
        self.assertEquals(self.repo.hg_branch(), "test_branch")
        branches = self.repo.get_branches()
        self.assertEquals(len(branches), 2)
        branch_names = self.repo.get_branch_names()
        self.assertEquals(len(branch_names), 2)

    def test_240_clone(self):
        if os.path.exists(self._clone1_path): shutil.rmtree(self._clone1_path)
        repo = hgapi.Repo.hg_clone(self._clone1_path, self._test_dir_path, user='testuser')
        self.assertTrue(os.path.exists(self._clone1_path))
        self.assertTrue(os.path.exists(self._clone1_file('file3.txt')))
        shutil.rmtree(self._clone1_path)
        self.assertFalse(os.path.exists(self._clone1_path))

    def test_241_clone_dir_exists_raises(self):
        dirName = self._clone2_path
        if os.path.exists(dirName): shutil.rmtree(dirName)
        os.makedirs(dirName)
        self.assertRaises(hgapi.HGError, lambda: hgapi.Repo.hg_clone(dirName, self._test_dir_path, user=self._user))
        shutil.rmtree(dirName)
        self.assertFalse(os.path.exists(dirName))

    def test_242_clone_dir_exists_OK(self):
        dirName = self._clone2_path
        if os.path.exists(dirName): shutil.rmtree(dirName)
        os.makedirs(dirName)
        repo = hgapi.Repo.hg_clone(dirName, self._test_dir_path, user=self._user, ok_if_local_dir_exists=True)
        self.assertTrue(os.path.exists(dirName))
        shutil.rmtree(dirName)
        self.assertFalse(os.path.exists(dirName))

    def test_243_clone_disable_host_key_checking(self):
        dirName = self._clone2_path
        if os.path.exists(dirName): shutil.rmtree(dirName)
        repo = hgapi.Repo.hg_clone(dirName, self._test_dir_path, user=self._user, disable_host_key_checking=True, ok_if_local_dir_exists=True)
        self.assertTrue(os.path.exists(dirName))
        shutil.rmtree(dirName)
        self.assertFalse(os.path.exists(dirName))

    def test_250_paths(self):
        dirName = self._clone1_path
        if os.path.exists(dirName): shutil.rmtree(dirName)
        repo = hgapi.Repo.hg_clone(dirName, self._test_dir_path, user='testuser')
        self.assertEqual({u'default' : self._test_dir_path}, repo.hg_paths())
        self.assertEqual(os.path.abspath(self._test_dir_path), repo.hg_path('default'))
        shutil.rmtree(dirName)
        self.assertFalse(os.path.exists(dirName))

    def test_260_resolve(self):
        # Switch to default branch and make changes
        self.repo.hg_update('default')

        # Note the start point
        start = self.repo.hg_node()

        with open(self._test_file('file2.txt'), "a+") as out:
            out.write("resolve_stuff1")
        self.repo.hg_commit('First change to file2')
        ch1 = self.repo.hg_node()

        # Switch to default branch and make different changes
        self.repo.hg_update(start)
        with open(self._test_file('file2.txt'), "a+") as out:
            out.write("resolve_stuff2")
        self.repo.hg_commit('Different change to file2')
        ch2 = self.repo.hg_node()

        # Switch back to the first set of changes
        self.repo.hg_update(ch1)
        # Attempt to merge in the second
        self.assertRaises(hgapi.HGUnresolvedFiles, lambda: self.repo.hg_merge(ch2, tool=hgapi.MERGETOOL_INTERNAL_FAIL))

        # Check that hg_resolve_list gets us the expected list of unresolved files
        self.assertEqual(hgapi.ResolveState(unresolved=[u'file2.txt']), self.repo.hg_resolve_list())
        # Try marking them as resolved
        self.repo.hg_resolve_mark_as_resolved()
        self.assertEqual(hgapi.ResolveState(resolved=[u'file2.txt']), self.repo.hg_resolve_list())
        # Try marking them as unresolved
        self.repo.hg_resolve_mark_as_unresolved()
        self.assertEqual(hgapi.ResolveState(unresolved=[u'file2.txt']), self.repo.hg_resolve_list())
        # Try remerging, fail
        self.assertRaises(hgapi.HGResolveFailed, lambda: self.repo.hg_resolve_remerge(tool=hgapi.MERGETOOL_INTERNAL_FAIL))
        self.assertEqual(hgapi.ResolveState(unresolved=[u'file2.txt']), self.repo.hg_resolve_list())
        # Try remerging
        self.repo.hg_resolve_remerge(tool=hgapi.MERGETOOL_INTERNAL_LOCAL)
        self.assertEqual(hgapi.ResolveState(resolved=[u'file2.txt']), self.repo.hg_resolve_list())

        # Commit the changes
        self.repo.hg_commit('Merge')



    def test_270_custom_merge(self):
        # Switch to default branch and make changes
        self.repo.hg_update('default')

        # Note the start point
        start = self.repo.hg_node()

        with open(self._test_file('file3.txt'), "a+") as out:
            out.write("resolve_stuff1")
        self.repo.hg_commit('First change to file3')
        ch1 = self.repo.hg_node()

        # Switch to default branch and make different changes
        self.repo.hg_update(start)
        with open(self._test_file('file3.txt'), "a+") as out:
            out.write("resolve_stuff2")
        self.repo.hg_commit('Different change to file3')
        ch2 = self.repo.hg_node()

        # Switch back to the first set of changes
        self.repo.hg_update(ch1)
        # Attempt to merge in the second
        merge_state = self.repo.hg_merge_custom(ch2)

        # There should be one unresolved file
        self.assertEqual({u'file3.txt'}, merge_state.unresolved)

        # Check the existance of the base, local and other files
        self.assertTrue(os.path.exists(self._test_file('file3.txt.base')))
        self.assertTrue(os.path.exists(self._test_file('file3.txt.local')))
        self.assertTrue(os.path.exists(self._test_file('file3.txt.other')))

        # Check contents
        self.assertEqual('this is more stuff', self._file_contents(self._test_file('file3.txt.base')))
        self.assertEqual('this is more stuff' + 'resolve_stuff1', self._file_contents(self._test_file('file3.txt.local')))
        self.assertEqual('this is more stuff' + 'resolve_stuff2', self._file_contents(self._test_file('file3.txt.other')))

        # Resolve - take local
        self.repo.hg_resolve_custom_take_local('file3.txt')

        # Check the state obtained from hg_resolve_list
        self.assertEqual(hgapi.ResolveState(resolved=[u'file3.txt']), self.repo.hg_resolve_list())

        # Clear the merge files
        self.repo.remove_merge_files('file3.txt')

        # Check that the base, local and other files no longer exist
        self.assertFalse(os.path.exists(self._test_file('file3.txt.base')))
        self.assertFalse(os.path.exists(self._test_file('file3.txt.local')))
        self.assertFalse(os.path.exists(self._test_file('file3.txt.other')))

        # Check the state obtained from hg_resolve_list
        self.assertEqual(hgapi.ResolveState(resolved=[u'file3.txt']), self.repo.hg_resolve_list())

        # Commit the changes
        self.repo.hg_commit('Custom Merge')



    def test_280_repo_config(self):
        config = self.repo.read_repo_config()
        self.assertFalse(config.has_option('extensions', 'rebase'))
        self.repo.enable_extension('rebase')
        config = self.repo.read_repo_config()
        self.assertTrue(config.has_option('extensions', 'rebase'))
        config.remove_option('extensions', 'rebase')
        self.repo.write_repo_config(config)

    def test_290_extensions(self):
        self.assertFalse(self.repo.is_extension_enabled('transplant'))
        self.repo.enable_extension('transplant')
        self.assertTrue(self.repo.is_extension_enabled('transplant'))
        config = self.repo.read_repo_config()
        config.remove_option('extensions', 'transplant')
        self.repo.write_repo_config(config)

    def test_300_rebase(self):
        self.repo.hg_update('default')

        #Store this version
        parent_node = self.repo.hg_node()
        parent_rev = self.repo.revision(parent_node)

        #creates new head
        with open(self._test_file('file4.txt'), "w") as out:
            out.write("this is more stuff")
        self.repo.hg_add("file4.txt")
        self.repo.hg_commit("adding file4 - pre rebase", user="test")
        default_child_node = self.repo.hg_node()
        default_child_rev = self.repo.revision(default_child_node)

        self.repo.hg_update(parent_node)

        #create head with branch
        with open(self._test_file('file5.txt'), "w") as out:
            out.write("this is more stuff")
        self.repo.hg_add("file5.txt")
        self.repo.hg_branch('rebase_branch')
        self.repo.hg_commit('adding file5 for rebase branch', user='test')
        rebase_child_node = self.repo.hg_node()
        rebase_child_rev = self.repo.revision(rebase_child_node)

        # check the structure: rebase_child -> parent  and  default_child -> parent
        self.assertEqual(default_child_rev.parents, [parent_rev.rev])
        self.assertEqual(rebase_child_rev.parents, [parent_rev.rev])


        # Now try rebasing
        # Ensure that it failed without first enabling the extension
        self.assertRaises(hgapi.HGExtensionDisabledError, lambda: self.repo.hg_rebase(rebase_child_node, default_child_node))

        # Now enable and try again
        self.repo.enable_rebase()
        self.repo.hg_rebase(rebase_child_node, default_child_node)

        # Check the new structure
        new_default_rev = self.repo.revision('default')

        self.assertEqual(new_default_rev.parents, [default_child_rev.rev])


    def test_310_user_config(self):
        # Read the config and ensure option does not exist
        config = self.repo.read_user_config()
        self.assertFalse(config.has_section('hgapi_test'))
        self.assertFalse(config.has_option('hgapi_test', 'test_option'))

        # Add the section and the option, and write
        config.add_section('hgapi_test')
        config.set('hgapi_test', 'test_option', 'hello')
        self.repo.write_user_config(config)

        # Read back, check existence of section and value
        config = self.repo.read_user_config()
        self.assertTrue(config.has_section('hgapi_test'))
        self.assertEqual(config.get('hgapi_test', 'test_option'), 'hello')

        # Now remove
        config.remove_option('hgapi_test', 'test_option')
        config.remove_section('hgapi_test')
        self.repo.write_user_config(config)

        # Read the config and ensure option does not exist
        config = self.repo.read_user_config()
        self.assertFalse(config.has_section('hgapi_test'))
        self.assertFalse(config.has_option('hgapi_test', 'test_option'))


    def test_320_archive(self):
        out_file, out_filename = tempfile.mkstemp(suffix='.zip')
        os.close(out_file)

        self.repo.hg_archive(out_filename, revision=TestHgAPI.__rev_after_test_copy, archive_type=hgapi.Repo.ARCHIVETYPE_ZIP, prefix='ark')

        zip_archive = zipfile.ZipFile(out_filename)
        names = set(zip_archive.namelist())
        zip_archive.close()

        self.assertEqual(names, {'ark/file.txt', 'ark/file_moved.txt', 'ark/copy_of_file_moved.txt', 'ark/.hg_archival.txt'})

        os.remove(out_filename)


    def test_330_pull(self):
        if os.path.exists(self._clone1_path): shutil.rmtree(self._clone1_path)
        clone_repo = hgapi.Repo.hg_clone(self._clone1_path, self._test_dir_path, user='testuser')
        self.assertTrue(os.path.exists(self._clone1_path))

        self.assertFalse(os.path.exists(self._clone1_file('file6.txt')))

        with open(self._test_file('file6.txt'), "w") as out:
            out.write("created in the main repo")
        self.repo.hg_add('file6.txt')
        self.repo.hg_commit('Added file6.txt')

        self.assertTrue(os.path.exists(self._test_file('file6.txt')))
        self.assertFalse(os.path.exists(self._clone1_file('file6.txt')))

        tasks = []
        def progress_listener(task):
            tasks.append(task)

        clone_repo.hg_pull(progress_listener=progress_listener)
        clone_repo.hg_update('default')
        self.maxDiff = None

        self.assertEqual([
            u'pulling from {0}'.format(self._test_dir_path),
            u'searching for changes',
            u'all local heads known remotely',
            #u'all heads known remotely',
            u'1 changesets found',
            u'adding changesets',
            u'adding manifests',
            u'adding file changes',
            u'added 1 changesets with 1 changes to 1 files'
        ], tasks)

        self.assertTrue(os.path.exists(self._test_file('file6.txt')))
        self.assertTrue(os.path.exists(self._clone1_file('file6.txt')))

        shutil.rmtree(self._clone1_path)
        self.assertFalse(os.path.exists(self._clone1_path))


    def test_340_push(self):
        if os.path.exists(self._clone1_path): shutil.rmtree(self._clone1_path)
        clone_repo = hgapi.Repo.hg_clone(self._clone1_path, self._test_dir_path, user='testuser')
        self.assertTrue(os.path.exists(self._clone1_path))

        self.assertFalse(os.path.exists(self._clone1_file('file7.txt')))

        with open(self._clone1_file('file7.txt'), "w") as out:
            out.write("created in the clone repo")
        clone_repo.hg_add('file7.txt')
        clone_repo.hg_commit('Added file7.txt')

        self.assertFalse(os.path.exists(self._test_file('file7.txt')))
        self.assertTrue(os.path.exists(self._clone1_file('file7.txt')))

        tasks = []
        def progress_listener(task):
            tasks.append(task)

        clone_repo.hg_push(progress_listener=progress_listener)
        self.repo.hg_update('default')

        self.assertEqual([
            u'pushing to {0}'.format(self._test_dir_path),
            u'searching for changes',
            u'1 changesets found',
            u'adding changesets',
            u'adding manifests',
            u'adding file changes',
            u'added 1 changesets with 1 changes to 1 files'
        ], tasks)

        self.assertTrue(os.path.exists(self._test_file('file7.txt')))
        self.assertTrue(os.path.exists(self._clone1_file('file7.txt')))

        shutil.rmtree(self._clone1_path)
        self.assertFalse(os.path.exists(self._clone1_path))


    def test_350_pull_from_unrelated(self):
        original_repo_path = tempfile.mkdtemp(prefix='testhgapi_original')
        main_clone_path = tempfile.mkdtemp(prefix='testhgapi_main_clone')


        try:
            # Create the original repo
            original_repo = hgapi.Repo.hg_init(original_repo_path, user=self._user)
            # Create and add a file, commit
            with open(os.path.join(original_repo_path, '1_file.txt'), 'w') as out:
                out.write("stuff\n")
            original_repo.hg_add("1_file.txt")
            original_repo.hg_commit("adding", user="test")

            # Make a clone repo
            main_clone = hgapi.Repo.hg_clone(main_clone_path, original_repo_path, user='testuser', ok_if_local_dir_exists=True)
            main_clone.hg_pull()
            main_clone.hg_update(None)

            # Ensure that 1_file.txt has made it over
            self.assertTrue(os.path.exists(os.path.join(main_clone_path, '1_file.txt')))

            # Add another file to the original and commit
            with open(os.path.join(original_repo_path, '1_file_2.txt'), 'w') as out:
                out.write("stuff\n")
            original_repo.hg_add("1_file_2.txt")
            original_repo.hg_commit("adding 2", user="test")

            # Pull and update in the clone
            main_clone.hg_pull()
            main_clone.hg_update(None)

            # Ensure that 1_file_2.txt has made it over
            self.assertTrue(os.path.exists(os.path.join(main_clone_path, '1_file_2.txt')))


            # Delete the original repo
            shutil.rmtree(original_repo_path)
            del original_repo

            # Remake the directory
            os.makedirs(original_repo_path)

            # Create a new repo there
            replacement_repo = hgapi.Repo.hg_init(original_repo_path, user=self._user)
            # Create and add a file, commit
            with open(os.path.join(original_repo_path, '2_file.txt'), 'w') as out:
                out.write("stuff\n")
            replacement_repo.hg_add("2_file.txt")
            replacement_repo.hg_commit("2-adding", user="test")


            # Attempt a pull; should raise HGRepoUnrelated
            self.assertRaises(hgapi.HGRepoUnrelated, lambda: main_clone.hg_pull())

            # Attempt a push; should raise HGRepoUnrelated
            self.assertRaises(hgapi.HGRepoUnrelated, lambda: main_clone.hg_push())

        finally:
            shutil.rmtree(original_repo_path)
            shutil.rmtree(main_clone_path)









def test_doc():
    #Prepare for doctest
    os.mkdir("./test_hgapi")
    with open("test_hgapi/file.txt", "w") as target:
        w = target.write("stuff")
    try:
        #Run doctest
        res = doctest.testfile("../README.rst")
    finally:
        #Cleanup
        shutil.rmtree("test_hgapi")

if __name__ == "__main__":
    import sys
    try:
        test_doc()
    finally:
        unittest.main()
    
