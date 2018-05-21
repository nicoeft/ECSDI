# -*- coding: utf-8 -*-
"""
filename: AgenteCliente

Antes de ejecutar hay que añadir la raiz del proyecto a la variable PYTHONPATH

Agente que interacciona con el usuario


Created on 09/02/2014

@author: amazon2
"""

from __future__ import print_function
from multiprocessing import Process
import socket
import argparse

from flask import Flask, render_template, request
from rdflib import Graph, Namespace, RDF, URIRef, Literal, XSD
from rdflib.namespace import FOAF, RDF
import requests

from AgentUtil.OntoNamespaces import ACL, DSO, AM2, RESTRICTION
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.ACLMessages import build_message, send_message, directory_search_agent
from AgentUtil.Agent import Agent
from AgentUtil.Logging import config_logger

__author__ = 'amazon2'

# Definimos los parametros de la linea de comandos
parser = argparse.ArgumentParser()
parser.add_argument('--open', help="Define si el servidor est abierto al exterior o no", action='store_true',
                    default=False)
parser.add_argument('--port', type=int, help="Puerto de comunicacion del agente")
parser.add_argument('--dhost', default='localhost', help="Host del agente de directorio")
parser.add_argument('--dport', type=int, help="Puerto de comunicacion del agente de directorio")

# Logging
logger = config_logger(level=1)

# parsing de los parametros de la linea de comandos
args = parser.parse_args()

# Configuration stuff
if args.port is None:
    port = 9010
else:
    port = args.port

if args.open is None:
    hostname = '0.0.0.0'
else:
    hostname = "localhost"
    # hostname = socket.gethostname()

if args.dport is None:
    dport = 9000
else:
    dport = args.dport

if args.dhost is None:
    dhostname = socket.gethostname()
else:
    dhostname = args.dhost

# Flask stuff
app = Flask(__name__)

# Configuration constants and variables
agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0

# Datos del Agente
AgenteCliente = Agent('AgenteCliente',
                       agn.AgenteCliente,
                       'http://%s:%d/comm' % (hostname, port),
                       'http://%s:%d/Stop' % (hostname, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:%d/Register' % (dhostname, dport),
                       'http://%s:%d/Stop' % (dhostname, dport))

# Global dsgraph triplestore
dsgraph = Graph()


def infoagent_search_message(addr, ragn_uri):
    """
    Envia una accion a un agente de informacion
    """
    global mss_cnt
    logger.info('Hacemos una peticion a AgenteMostrarProductos')

    gmess = Graph()
    
    gmess.bind('foaf', FOAF)
    gmess.bind('am2', AM2)
     # Creamos el sujeto -> contenido del mensaje
    sj_contenido = agn[AgenteCliente.name + 'Peticion_productos_disponibles' + str(mss_cnt)]
    #le damos un tipo
    gmess.add((sj_contenido, RDF.type, AM2.Peticion_productos_disponibles))
    
    # Añadimos restriccion modelo
    sj_modelo = AM2['Modelo' + str(mss_cnt)] #creamos una instancia con nombre Modelo1
    gmess.add((sj_modelo, RDF.type, AM2['Restriccion'])) # indicamos que es de tipo Modelo
    gmess.add((sj_modelo, RESTRICTION.tipoRestriccion, AM2['Restriccion_modelo'])) # indicamos que es de tipo Modelo
    gmess.add((sj_modelo, AM2.tieneModelo, Literal('E1234H'))) #le damos valor a su data property
    
    #añadimos el modelo al conenido con su object property
    gmess.add((sj_contenido, AM2.Restricciones_clientes, URIRef(sj_contenido))) 

    # for s,p,o in gmess:
    #     logger.info('[gmess] sujeto:%s | predicado: %s | objeto: %s', s, p,o)

    msg = build_message(gmess, perf=ACL.request,
                        sender=AgenteCliente.uri,
                        receiver=ragn_uri,
                        content=sj_contenido,
                        msgcnt=mss_cnt)
    gr = send_message(msg, addr)
    mss_cnt += 1
    logger.info('Recibimos respuesta a la peticion al servicio de informacion')

    return gr


@app.route("/iface", methods=['GET', 'POST'])
def browser_iface():
    """
    Permite la comunicacion con el agente via un navegador
    via un formulario
    """
    if request.method == 'GET':
        return render_template('iface.html')
    else:
        user = request.form['username']
        mess = request.form['message']
        return render_template('riface.html', user=user, mess=mess)


@app.route("/Stop")
def stop():
    """
    Entrypoint que para el agente

    :return:
    """
    tidyup()
    shutdown_server()
    return "Parando Servidor"


@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicacion del agente
    """
    return "Hola"


def tidyup():
    """
    Acciones previas a parar el agente

    """
    pass


def agentbehavior1():
    """
    Un comportamiento del agente

    :return:
    """

    # Buscamos en el directorio
    # un agente de mostrar productos
    logger.info('Buscamos en el servicio de registro')
    AgenteMostrarProductos = directory_search_agent(DSO.AgenteMostrarProductos,AgenteCliente,DirectoryAgent,mss_cnt)
    logger.info('Recibimos informacion del agente')


    # Ahora mandamos un objeto de tipo request mandando una accion de tipo Search
    # que esta en una supuesta ontologia de acciones de agentes
    gr = infoagent_search_message(AgenteMostrarProductos.address,AgenteMostrarProductos.uri)

    # for s,p,o in gr:
    #     logger.info('sujeto:%s | predicado: %s | objeto: %s', s, p,o)

    for s,p,o in gr.triples( (None,  RDF.type, AM2.Producto) ):
        print('Producto: sujeto:%s | predicado: %s | objeto: %s'%( s, p,o))
        for s2,p2,o2 in gr.triples((s,None,None)):
            print ('Propiedades: %s | %s | %s'%( s2, p2, o2))

    # gr2 = infoagent_search_message(AgenteMostrarProductos.address,AgenteMostrarProductos.uri)
    # gr3 = infoagent_search_message(AgenteMostrarProductos.address,AgenteMostrarProductos.uri)
    
    
    # r = requests.get(ra_stop)
    # print r.text

    # Selfdestruct
    requests.get(AgenteCliente.stop)


if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1)
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    logger.info('The End')
