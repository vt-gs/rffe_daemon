import logging
import pika
import json
from sortedcontainers import SortedDict
from brokerconnector import BrokerConnector

#class BrokerProducer(BrokerConnector):
    # """BrokerProducer provides basic functionality to support the connection
    # needed for a typical Pika to RabbitMQ producer connection.  Individual
    # functions could be overridden if alternate or additional functionality is
    # desired.  Derived classes would override the "send and/or "publish_message"
    # functions.
    # """
    #
    # def __init__(self, amqp_url, exchange, exchange_type='direct',
    #              queue='', loggername=None,
    #              app_name=None, updatedelay=1.0):
    #     """Create a new instance of the consumer class, passing in the RabbitMQ
    #     connection URL and exchange/routing information.  The specified exchange
    #     will be created if it does not exist.
    #
    #     :param str amqp_url:      The Rabbit connection url.
    #     :param str exchang:       The name of the exchange to interact with.
    #     :param str exchange_type: The RabbitMQ exchange type.  If the exchange
    #                               already exists the type _must_ agree with
    #                               the existing value or an error will be thrown.
    #     :param str queue:         The name of the queue used for interaction.  If
    #                               the string is empty (the default) a new, unique
    #                               queue will be created by RabbitMQ.
    #     """
    #     super(BrokerProducer, self).__init__(amqp_url, exchange,
    #           exchange_type, queue, loggername)
    #     self.update_delay = updatedelay
    #     self.delivery_queue = SortedDict()
    #     self.message_number = 1
    #     self.app_name = app_name
class BrokerProducer(BrokerConnector):
    """BrokerProducer provides basic functionality to support the connection
    dneeded for a typical Pika to RabbitMQ producer connection.  Individual
    functions could be overridden if alternate or additional functionality is
    desired.  Derived classes would override the "send and/or "publish_message"
    functions.
    """


    def __init__(self, cfg, loggername=None):
        super(BrokerProducer, self).__init__(cfg, loggername)

        self.update_delay = 0.1
        self.delivery_queue = SortedDict()
        self.message_number = 1
        self.app_name = cfg['app_name']

    def send(self, message, key):
        """Add the provided message to the "queue" of messages to be sent.  It
        is assumed (and required) that the message is a dictionary that represents
        a JSON object to be sent.  The message over the wire is "stringified"
        via a call to json.dumps().
        """
        if self.loggername is not None:
            self.logger.debug('Accepted message bound for "{}"'.format(key))
        # DANGER: we're adding the message and incrementing the message ID/number
        # with no gaurds.  This likely means we are _not_ thread safe.  That is
        # calls to send from different threads my collide.  This should be
        # reviewed/fixed in the future.
        self.delivery_queue[str(self.message_number)] = (message, key)
        self.message_number += 1


    def on_exchange_declareok(self, frame):
        """Called when the server has finished the creation of the exchange.
        """
        if self.loggername is not None:
            self.logger.debug('Exchange declared successfully')
        self.start_publishing()

    def start_publishing(self):
        """Begin sending messages.  The enable_delivery_confirmations function
        isfirst called which, in this class, enables notification of delivery
        of messages to the broker.  If derived classes don't want notifications
        that function can be overridden (e.g. with a 'pass').
        """
        if self.loggername is not None:
            self.logger.info('Registering as producer with broker')
        self.enable_delivery_confirmations()
        self.schedule_next_message()

    def enable_delivery_confirmations(self):
        """Sends a request for delivery notifications (ACKs) to the broker
        and registers the on_delivery_confirmation function as the notification
        callback.
        """
        self.channel.confirm_delivery(self.on_delivery_confirmation)

    def on_delivery_confirmation(self, method_frame):
        """Function called with message delivery notifications.  The supplied
        method_frame.method.NAME will hold the notification type (ACK, NACK, etc.)
        """
        confirmation_type = method_frame.method.NAME.split('.')[1].lower()
        if confirmation_type != 'ack':
            if self.loggername is not None:
                self.logger.info("No ACK from broker on message: {}".format(confirmation_type))

        # DANGER: here we're assuming that the delivery_tag is the same as the
        # message_id.  We're setting the message_id to a sequential number that
        # starts at 1 within the "send" function.  Since RabbitMQ delivery tags
        # follow this method we should be OK but if anything changes this won't
        # wotk.  We sent the messa_id and correlation_id in the properties in
        # the Pika basic_publish call but those don't seem to be returned with
        # the acknowledge.  I either be doing something wrong or Pika (or RabbitMQ)
        # is missing something.  There doesn't seem to be a way to get the value
        # of the delivery_tag on send so I don't know how to tied the send to
        # the ACK!
        del self.delivery_queue[str(method_frame.method.delivery_tag)]

    def schedule_next_message(self):
        if self.closing:
            return
        self.connection.add_timeout(self.update_delay,
                                    self.publish_message)

    def publish_message(self):
        if self.closing:
            return

        if self.delivery_queue:
            # message queue is not empty, send the first (i.e. FIFO) message
            (id, (message,key)) = self.delivery_queue.peekitem(0)

            if self.loggername is not None:
                self.logger.debug('Publishing message bound for "{}"'.format(key))

            properties = pika.BasicProperties(app_id=self.app_name,
                                              content_type='application/json',
                                              message_id=id,
                                              correlation_id=id)
            self.channel.basic_publish(self.exchange, key,
                                        json.dumps(message, ensure_ascii=False),
                                        properties)

        self.schedule_next_message()
