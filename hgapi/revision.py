class Revision(object):
    """A representation of a revision.
    Available fields are::

      node, rev, author, branch, parents, date, tags, desc

    A Revision object is equal to any other object with the same value for node
    """
    def __init__(self, node, rev, author, branch, parents, date, tags, desc):
        self.node = node
        self.rev = rev
        self.author = author
        self.branch = branch
        self.parents = parents
        self.date = date
        self.tags = tags
        self.desc = desc


    def __iter__(self):
        return self


    def __eq__(self, other):
        """Returns true if self.node == other.node"""
        if isinstance(other, Revision):
            return self.node == other.node
        else:
            return NotImplemented


    def __ne__(self, other):
        """Returns true if self.node != other.node"""
        if isinstance(other, Revision):
            return self.node != other.node
        else:
            return NotImplemented


    def __hash__(self):
        return hash(self.node)





