class Status (object):
    """A representation of a repo status.
    Available fields are:
    added
    modified
    removed
    untracked
    missing
    """
    def __init__(self, added=None, modified=None, removed=None, untracked=None, missing=None):
        self.added = set(added)   if added is not None   else set()
        self.modified = set(modified)   if modified is not None   else set()
        self.removed = set(removed)   if removed is not None   else set()
        self.untracked = set(untracked)   if untracked is not None   else set()
        self.missing = set(missing)   if missing is not None   else set()


    @property
    def has_any_changes(self):
        return len(self.added) > 0  or  len(self.modified) > 0  or  len(self.removed) > 0  or\
               len(self.untracked) > 0  or  len(self.missing)  >  0


    @property
    def has_uncommitted_changes(self):
        return len(self.added) > 0  or  len(self.modified) > 0  or  len(self.removed) > 0


    @property
    def has_uncommitted_changes_or_missing_files(self):
        return len(self.added) > 0  or  len(self.modified) > 0  or  len(self.removed) > 0  or  len(self.missing)  >  0


    @property
    def has_added_files(self):
        return len(self.added) > 0

    @property
    def has_modified_files(self):
        return len(self.modified) > 0

    @property
    def has_removed_files(self):
        return len(self.removed) > 0

    @property
    def has_untracked_files(self):
        return len(self.untracked) > 0

    @property
    def has_missing_files(self):
        return len(self.missing) > 0


    def __eq__(self, other):
        if isinstance(other, Status):
            return self.added == other.added  and  self.modified == other.modified  and\
                   self.untracked == other.untracked  and  self.missing == other.missing  and\
                   self.removed == other.removed
        else:
            return NotImplemented


    def __ne__(self, other):
        if isinstance(other, Status):
            return self.added != other.added  or  self.modified != other.modified  or\
                   self.untracked != other.untracked  or  self.missing != other.missing  or\
                   self.removed != other.removed
        else:
            return NotImplemented


    def __repr__(self):
        return 'Status(added={0}, modified={1}, removed={2}, untracked={3}, missing={4})'.format(repr(self.added),
            repr(self.modified), repr(self.removed), repr(self.untracked), repr(self.missing))

    def __str__(self):
        return 'Status(added={0}, modified={1}, removed={2}, untracked={3}, missing={4})'.format(self.added,
            self.modified, self.removed, self.untracked, self.missing)






class ResolveState (object):
    """A representation of a repo resolve state.
    Available fields are:
    unresolved
    resolved
    """
    def __init__(self, unresolved=None, resolved=None):
        self.unresolved = set(unresolved)   if unresolved is not None   else set()
        self.resolved = set(resolved)   if resolved is not None   else set()


    @property
    def has_any_files(self):
        return len(self.unresolved) > 0  or  len(self.resolved) > 0

    @property
    def has_unresolved_files(self):
        return len(self.unresolved) > 0

    @property
    def has_resolved_files(self):
        return len(self.resolved) > 0


    def __eq__(self, other):
        if isinstance(other, ResolveState):
            return self.unresolved == other.unresolved  and  self.resolved == other.resolved
        else:
            return NotImplemented


    def __ne__(self, other):
        if isinstance(other, ResolveState):
            return self.unresolved != other.unresolved  or  self.resolved != other.resolved
        else:
            return NotImplemented


    def __repr__(self):
        return 'ResolveState(unresolved={0}, resolved={1})'.format(repr(self.unresolved), repr(self.resolved))

    def __str__(self):
        return 'ResolveState(unresolved={0}, resolved={1})'.format(self.unresolved, self.resolved)


