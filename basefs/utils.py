import os


class Candidate(object):
    def __init__(self, score, entry):
        self.score = score
        self.entry = entry
    
    def __gt__(self, candidate):
        """ self better than candidate """
        return (
            self.score > candidate.score or (
                self.score == candidate.score and self.entry.hash > candidate.entry.hash)
        )


def is_subdir(path, directory):
    path = os.path.realpath(path)
    directory = os.path.realpath(directory)
    relative = os.path.relpath(path, directory)
    if relative.startswith(os.pardir):
        return False
    else:
        return True

