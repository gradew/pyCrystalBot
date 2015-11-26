#!/usr/bin/env python
import pika
import sys,time

connection = pika.BlockingConnection(pika.ConnectionParameters(
        host='localhost'))
channel = connection.channel()

channel.exchange_declare(exchange='pycrystalbot_cmd',
                         type='fanout')

message = ' '.join(sys.argv[1:]) or "info: Hello World!"
channel.basic_publish(exchange='pycrystalbot_cmd',
                      routing_key='',
                      body=message)
print " [x] Sent %r" % (message,)
connection.close()
