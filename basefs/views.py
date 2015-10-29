from basefs.exceptions import IntegrityError


class ViewNode(object):
    def __init__(self, entry):
        self.entry = entry
        self.childs = []
    
    def mkdir(self, path):
        self.entry.mkdir(path)
        self.build(self.log)
    
    def write(self, content):
        parent = getattr(self, 'future_parent', self)
        parent.entry.write(self.entry.path, content)
        parent.build(parent.log)
    
    def create(self, path):
        entry = type(self.log)(self.entry, LogEntry.WRITE, path, '')
        entry.ctime = int(time.time())
        entry.time = entry.ctime
        node = View(entry)
        node.future_parent = self
        self.paths[path] = node


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


class View(object):
    def __init__(self, log):
        self.log = log
    
    def build(self):
        keys = self.log.root_keys.read_keys()
        __, __, paths, root = self.rec_build(self.log.root, keys)
        self.paths = paths
        self.root = root
        return self.root
    
    def rec_build(self, entry, keys):
        # TODO copy.copy instead of deepcopy
        if entry.action != entry.MKDIR:
            raise entry.IntegrityError("WTF are you calling rec_build on?")
        # Lookup for delete+mkdir pattern
        score, state = entry.find_branch_state(keys)
        if state == [None]*4:
            return
        node = ViewNode(state)
        paths = {
            entry.path: node
        }
        childs = defaultdict(list)
        for child in entry.childs:
            # same path branch has been already inspected
            if entry.path != child.path:
                childs[child.path].append(child)
        keys_path = os.path.join(entry.path, '.keys')
        key_entries = childs.pop(keys_path, None)
        if key_entries:
            # lookup for keys
            key_score, key_state = entry.find_branch_state(copy.deepcopy(keys), *key_entries)
            if key_state:
                score += key_score
                key_node = ViewNode(key_state)
                node.childs.append(key_node)
                paths[key_state.path] = key_node
                keys.update(key_state.read_keys())
        for path, childs in childs.items():
            action = childs[0].action
            selected = None
            for child in childs:
                # MKDIR /hola, MKDIR /hola, WRITE /hola
                if action == entry.WRITE:
                    child_score, child_state = entry.find_branch_state(copy.deepcopy(keys), *childs)
                    child_node = ViewNode(child_state)
                    child_paths = {
                        path: child_node
                    }
                else:
                    # MKDIR
                    child_score, child_state, child_paths, child_node = self.rec_build(child, copy.deepcopy(keys))
                if child_state:
                    candidate = Candidate(score=child_score, entry=child)
                    if not selected or candidate > selected:
                        selected = candidate
                        selected.node = child_node
                        selected.paths = child_paths
            if selected:
                node.childs.append(selected.node)
                score = selected.score + score if score else selected.score
                paths.update(selected.paths)
        return score, state, paths, node
