import enum
from typing import *
from ..action import constructor
from . import data
from . import base
from ..eval import cache



class Status(enum.IntEnum):
    none = 0
    composed = 1
    assigned = 2
    determined = 3
    ready = 4
    submitted = 5
    running = 6
    finished = 7



class _TaskBase:

    no_value = cache.ResultCache.NoValue

    def __init__(self, action: 'dev._ActionBase', inputs: List['Atomic'],
                 parent: '_TaskBase', task_name: str):
        self.action = action
        # Action (like function definition) of the task (like function call).
        self.inputs = []
        # Input tasks for the action's arguments.
        self.outputs: List['Atomic'] = []
        # List of tasks dependent on the result. (Try to not use and eliminate.)
        self.id: int = 0
        # Task is identified by the hash of the hash of its parent task and its name within the parent.
        self.parent: Optional['Composed'] = parent
        # parent task
        self.child_id = None
        # name of current task within parent
        self.id = int
        # unique task hash
        self._set_id(parent, task_name)

        self.status = Status.none
        # Status of the task, possibly need not to be stored explicitly.
        self._result: Any = self.no_value
        # The task result.
        self._result_hash = None
        # Hash of the result
        self.resource_id = None

        self.start_time = -1
        self.end_time = -1
        self.eval_time = 0

        # Connect to inputs.
        for input in inputs:
            assert isinstance(input, _TaskBase)
            self.inputs.append(input)
            input.outputs.append(self)



    def action_hash(self):
        return self.action.action_hash()

    @property
    def priority(self):
        return 1

    @property
    def result(self):
        return self._result

    @property
    def result_hash(self):
        return self._result_hash

    def evaluate_fn(self):
        # Returns a function accepting the input data and computing the result.
        # e.g. action.evaluate
        assert False, "Not implemented."

    def lazy_hash(self):
        task_hash = self.action_hash()
        for input in self.inputs:
            task_hash = data.hash(input.result_hash, previous=task_hash)
        return task_hash

    def finish(self, result, task_hash):
        """
        Store the result of the action.
        :param result: The result value.
        :param task_hash: The hash of lazy evaluation of the value (hash of the action chain)
        :return:
        """
        assert result is not self.no_value
        self.status = Status.finished
        self._result = result
        self._result_hash = task_hash

    def is_finished(self):
        return self.result is not self.no_value

    def is_ready(self):
        assert False, "Not implemented."

    def get_path(self):
        path = []
        t = self
        while t is not None:
            path.append(t.child_id)
            t = t.parent
        return path

    def _set_id(self, parent_task, child_id):
        self.child_id = child_id
        if parent_task is None:
            parent_hash = data.hash(None)
        else:
            parent_hash = parent_task.id
        self.id = data.hash(child_id, previous=parent_hash)

    def __lt__(self, other):
        return self.priority < other.priority

    @staticmethod
    def _create_task(action, input_tasks, parent_task, child_name):
        """
        Create task from the given action and its input tasks.
        """
        task_type = action.task_type
        if task_type == base.TaskType.Atomic:
            child = Atomic(action, input_tasks, parent_task, child_name)
        elif task_type == base.TaskType.Composed:
            child = Composed(action, input_tasks, parent_task, child_name)
        else:
            assert False
        return child


class Atomic(_TaskBase):


    def is_ready(self):
        """
        Update ready status, return
        :return:
        """
        if self.status < Status.ready:
            is_ready = all([task.is_finished() for task in self.inputs])
            if is_ready:
                self.status = Status.ready
        return self.status == Status.ready

    def evaluate_fn(self):
        """
        For given data evaluate the action and store the result.
        TODO: should handle just status and possibly store the result
        since Resource may execute the task remotely.
        """
        assert self.is_ready()
        return self.action.evaluate



class ComposedHead(Atomic):
    """
    Auxiliary task for the inputs of the composed task. Simplifies
    expansion as we need not to change input and output links of outer tasks, just link between head and tail.
    """

    @classmethod
    def create(cls, i, input_task, parent, name):
        if name is None:
            name = "__head_{}".format(i)
        return cls(constructor.Pass(), [input_task], parent, name)

    @property
    def result(self):
        return self.inputs[0].result


class Composed(Atomic):
    """
    Composed tasks are non-leaf vertices of the execution tree.
    The Evaluation class takes care of their expansion during execution according to the
    preferences assigned by the Scheduler. It also keeps a map from
    """

    def __init__(self, action: 'dev._ActionBase', inputs: List['Atomic'],
                 parent: '_TaskBase', task_name: str):
        params = action.parameters
        assert params.size() == len(inputs)
        heads = [ComposedHead.create(i, input, parent, param.name)
                                        for (i, input), param in zip(enumerate(inputs), params)]
        super().__init__(action, heads, parent, task_name)
        self.time_estimate = 0
        # estimate of the start time, used as expansion priority
        self.childs: Atomic = None
        # map child_id to the child task, filled during expand.

    def is_ready(self):
        """
        Block submission of unexpanded tasks.
        :return:
        """
        return self.is_expanded() and Atomic.is_ready(self)


    def child(self, item: Union[int, str]) -> Optional[Atomic]:
        """
        Return subtask given by parameter 'item'
        :param item: A unique idenfication of the subtask. The name of the
        action_instance within a workflow, the loop index for ForEach and While actions.
        :return: The subtask or None if the item is no defined.
        """
        assert self.childs
        return self.childs.get(item, None)

    def invalidate(self):
        """
        Invalidate the task and its descendants in the execution DAG using the call tree.
        :return:
        """

    def is_expanded(self):
        return self.childs is not None


    def create_child_task(self, name, action, inputs):
        return _TaskBase._create_task(action, inputs, self, name)

    def expand(self):
        """
        Composed task expansion.

        Connect the head tasks to the body and the 'self' (i.e. the tail task) to the result
        action instance of the body. Auxiliary tasks for the heads, result and tail
        are used in order to minimize modification of the task links.

        :return:
            None if the expansion can not be performed, yet.
            Dictionary of child tasks (action_instance_name -> task)
            Empty dict is valid result, used to indicate end of a loop e.g. in the case of ForEach and While actions.
        """
        assert self.action.task_type == base.TaskType.Composed
        assert hasattr(self.action, 'expand')

        # Disconnect composed task heads.
        heads = self.inputs.copy()
        for head in heads:
            head.outputs = []
        # Generate and connect body tasks.
        childs = self.action.expand(self, self.create_child_task)
        if childs is not None:
            self.childs = {task.child_id: task for task in childs}
            result_task = self.childs['__result__']
            assert len(result_task.outputs) == 0
            result_task.outputs.append(self)
            self.inputs = [result_task]
            # After expansion the composed task is just a dummy task dependent on the previoous result.
            # This works with Workflow, see how it will work with other composed actions:
            # if, reduce (for, while)

        else:
            # No expansion: reconnect heads
            for head in heads:
                head.outputs = [self]
        return self.childs

    def evaluate_fn(self):
        """
        Composed tasks use evaluate to finish expansion.
        """
        assert self.is_ready()
        assert len(self.inputs) == 1
        return lambda x: x[0]



