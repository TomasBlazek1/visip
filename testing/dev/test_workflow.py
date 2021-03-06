from visip.dev import action_instance as instance
from visip.dev import action_workflow as wf
from visip.action import constructor

def test_workflow_modification():
    w = wf._Workflow("tst_wf")

    ## Slot modifications
    # insert_slot
    w.insert_slot(0, wf._SlotCall("a_slot"))
    w.insert_slot(1, wf._SlotCall("b_slot"))
    assert w.parameters.size() == 2
    assert w.parameters.get_index(0).name == 'a_slot'
    assert w.parameters.get_index(1).name == 'b_slot'

    # move_slot
    w.insert_slot(2, wf._SlotCall("c_slot"))
    # A B C
    w.move_slot(1, 2)
    # A C B
    assert w.parameters.get_index(2).name == 'b_slot'
    assert w.parameters.get_index(1).name == 'c_slot'
    w.move_slot(2, 0)
    # B A C
    assert w.parameters.get_index(0).name == 'b_slot'
    assert w.parameters.get_index(1).name == 'a_slot'
    assert w.parameters.get_index(2).name == 'c_slot'

    # remove_slot
    w.remove_slot(2)
    assert w.parameters.size() == 2

    ## ActionCall modifications
    result = w.result
    slots = w.slots
    list_action =  constructor.A_list()
    list_1 = instance.ActionCall.create(list_action)
    res = w.set_action_input(list_1, 0, slots[0])
    assert res
    res = w.set_action_input(list_1, 1, slots[1])
    assert res
    res = w.set_action_input(result, 0, list_1)
    assert res
    assert slots[0].output_actions[0][0] == list_1
    assert slots[1].output_actions[0][0] == list_1
    assert list_1.output_actions[0][0] == result
    assert list_1.name == 'list_1'
    assert len(w._action_calls) == 4
    # w:  (slot0 (B), slot2 (A)) -> List1 -> result

    ## ActionCall rename
    list_1.name ='list_2'
    assert list_1.name == 'list_2'
    assert sorted(list(w.action_call_dict.keys())) == ['__result__', 'a_slot', 'b_slot', 'list_2']


    # unlink
    w.set_action_input(list_1, 0, None)
    assert len(list_1.arguments) == 2
    assert list_1.arguments[0].value == None
    assert not slots[0].output_actions

    w.set_action_input(list_1, 1, None)
    assert len(list_1.arguments) == 0
    # w:  (slot0 (B), slot2 (A))  List1 -> result


    # Test cycle
    w.set_action_input(list_1, 0, slots[0])
    list_2 = instance.ActionCall.create(constructor.A_list())
    w.set_action_input(list_1, 1, list_2)
    # w:  (slot0 (B), List2) -> List1 -> result
    res = w.set_action_input(list_2, 0, list_1)     # Cycle
    assert not res
    assert len(list_2.arguments) == 0
