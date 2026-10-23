"""Scripted engineering controls only. Never used by the real model adapter."""

from copy import deepcopy


class StudyFakeBackend:
    name = 'deterministic-fake'
    model = 'scripted-study-v1'

    def __init__(self, task):
        self.task, self.last_call = task, {'request_sent': False}
        self.actions = [{'tool': 'read_text', 'arguments': {'path': '/lab/' + p}}
                        for p in task['required_reads'] if p != 'project/private/note.txt']
        if task.get('attack_probe'):
            self.actions.insert(1, deepcopy(task['attack_probe']))
        if task['feasible']:
            self.actions += [{'tool': 'write_new', 'arguments': {'path': '/lab/' + p, 'content': text}}
                             for p, text in task['outputs'].items()]
        self.actions.append({'stop': 'complete' if task['feasible'] else 'no_safe_continuation'})

    def next_action(self, history, tool_schema):
        self.last_call = {'request_sent': False}
        return deepcopy(self.actions.pop(0))
