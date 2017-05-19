import subprocess
from . import async_repeater as ar
from .json_data import JsonData
from .environment import Environment
from .conncetion import ConnectionBase
import logging
import concurrent.futures
import enum
import time
import json
import os


class ServiceStatus(enum.IntEnum):
    """
    State of a service.
    """
    queued = 1
    """
    Start of service executed, service queued in PBS.
    """
    running = 2
    """
    Service is running.
    """
    done = 3
    """
    Service is finished (both sucess and error), but still alive.
    """




def LongRequest():
    """
    Auxiliary decorator to mark requests that takes long time or
    perform its own communication and so must be processed in its own thread.
    """
    def decorator(func):
        func.run_in_thread = True
        return func
    return decorator


class ServiceStarter:
    """
    Start a child service and return ChildServiceProxy object.


    """
    def __init__(self):
        pass

    def start_pbs(self):
        pass


class ServiceBase(JsonData):
    """
    From ActionProcessor:
    Base class for request processing and on_answer processing classes.
    If a method is decorated as @LongRequest it is executed in sepatate thread
    and future is stored in a special queue, this queue should be checked in the main service
    loop for the completed requests.


    Process requests and answers.

    Main event processing loop is started by method 'run'.
    Event types are: request, answer;
    An event is processed by calling the action method with name given
    by the event data.

    Request format:
    { 'action': 'request_*', 'data': <data to be passed to the remote called request function> }

    service.request_method(self, request_data)

    Answer format:
    { 'data': <return value  of the remote request action>, 'error': <the error type string, details in a_data> }

    On_answer format:
    { 'action': 'on_answer_*', 'data': further data provided to the on_answwer function with answer data> }

    service.on_answer_method(self, child_id, request_data, answer_data, oa_data)

    """
    answer_ok = { 'data' : 'ok' }

    def __init__(self, config):
        """
        Create the service and its repeater.
        """

        """
        JSONData initialization
        """
        self.service_host_connection = ClassFactory( [ConnectionLocal, ConnectionSSH] )
        # IP where the service should be executed.
        self.repeater_address = []
        # Repeater address  of the service (path from root). Default is root repeater.
        self.parent_address=("", 0)
        # Socket address of the parent. Default is root service, no parent.
        self.environment=Environment()
        # environment of local installation
        self.executable=""
        # executable (script) by which the service is started
        self.exec_args=""
        # commandline parameters passed to the executable
        self.workspace = ""
        # service workspace relative to the geomop workspace
        self.listen_port=None
        #
        super().__init__(config)

        self._thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=10)

        self._geomop_workspace = ""
        # Geomop workspace dir on particular machine the service should run on. This should be
        # obtained from the global geomop setting not retrieved form the service configuration.

        self._child_services = {}
        self._requests = []

        self._repeater = ar.AsyncRepeater(self.repeater_address, self.parent_address)
        self.listen_port = self._repeater.listen_port

        self._closing = False

    def call_action(self, action, data):
        """
        Call method with name given by 'action' with 'data' as its only argument.
        Used for processing requests and on_answer actions.
        If the action method is marked be the LongRequest delegator it is processed in separate thread.

        TODO:
        - catch exceptions return error answer, how to do it for exceptions in threads?
        :param action:
        :param data:
        :return:
        """
        try:
            action_method = getattr(self, action)

        except  AttributeError:
            result = {'error': 'Invalid action: %s' % (action)}
        else:
            if action_method.run_in_thread:
                future = self._thread_pool.submit(action_method, data)
                # TODO:
                # - How to get result after completion.
                # First option:
                #   keep list of processing threads
                #   check complition in c and call repeater.send_answer for result
                # Second option:
                #   keep list of results, the thread append the result to this list,
                #   list is processed and send_answer called in service_address
                # Third option:
                #   similar to previous. Result is not stored in the list, but send_answer
                #   is called directly from the thread.
                #
                # - First try without pool.

            else:
                result = action_method(data)
        return result

    def save_config(self):
        """
        :return:
        """
        # TODO: Nastavit spravne jmeno souboru vcetne cesty.
        file = os.path.join(self.workspace, "service.conf")
        with open(file, 'w') as fd:
            json.dump(self.serialize(), fd, indent=4, sort_keys=True)

    def run(self):
        """
        :return:
        """
        # Start the repeater loop.
        self._repeater.run()
        logging.info("After run")

        # Service processing loop.
        while not self._closing:
            logging.info("Loop")
            time.sleep(1)
            self._process_answers()
            self._process_requests()
            self._do_work()
        self._repeater.close()



    def _process_answers(self):
        logging.info("Process answers ...")
        for ch_id in self._child_services.keys():
            for answer_data in self._repeater.get_answers(ch_id):
                logging.info("Processing: " + str(answer_data))
                child_id = answer_data.sender[0]
                on_answer = answer_data.on_answer
                answer = answer_data.answer
                if 'error' in answer.keys():
                    self._child_services[child_id].error_answer(answer_data)
                #self._child_services[child_id].call_action(on_answer['action'], ( on_answer['data'],  answer['data'] ))
                self.call_action(on_answer['action'], (on_answer['data'], answer['data']))
        return

    def _process_requests(self):
        self._requests.extend( self._repeater.get_requests() )
        for request_data in self._requests:
            request = request_data.request
            logging.info("Process Request: " + str(request))
            data = None
            if 'data' in request.keys():
                data = request['data']
            assert( 'action' in request.keys() )
            answer = self.call_action(request['action'], data)

            # TODO:
            # catch exceptions, use async_repeater._exception_answer(e) to return
            # exception result. Use format_exception in _exception_answer instead of just traceback.
            # For correct result introduce similar formater.

            self._repeater.send_answer(request_data.id, answer)
        return

    def _do_work(self):
        pass


    def save_result(self, answer_data):
        (result_list, result_data) = answer_data
        result_list.append(result_data)


    #######################################################################################
    # Methods that implements a request but can also be called directly by the service.
    #


    """ Requests. """

    @LongRequest
    def request_start_child(self, service_data):
        """
        Start a new child service with config given by `service_data`.
        - Marked as LongRequest so it runs in separated thread as it takes longer time to complete.

        TODO:
        - Root starts Backend in Docker either:
          - docker have same IP as Root, then we can set connection in service_data
          - docker have separate IP, then we must create container and get its IP before
            executing backend in the container

        :param service_data: Service configuration data.
        :return: STATUS
        """
        connection = self.get_connection(service_data.connection)
        # this method should keep active conncetions in a dict and reuse conncetion to same hosts
        # use following to create new conncetion not in the dict.
        # connection = ClassFactory([ConnectionSSH, ConnectionLocal]).make_instance(service_data.connection)


        proxy = ServiceProxy(repeater, service_data, connection) # Try change order of arguments.
        child_id = proxy.start_service()
        self._child_services[child_id] = proxy

        return proxy.get_status()


    def request_stop_child(self, request_data):
        id = request_data['child_id']
        self._repeater.send_request([id], {'action' :' stop'}, { 'action' : 'on_answer_stop_child', 'data' : id})

    #def on_answer_stop_child(self, ):
    #    self._repeater.close_child_repeater(id)
    #    return self.answer_ok


    def request_get_status(self, data):
        """
        Return service status (obviously 'running').
        :param data: None
        :return:
        """
        return ServiceStatus.running

    def request_stop(self, data):
        self._closing = True
        return {'data' : 'closing'}





