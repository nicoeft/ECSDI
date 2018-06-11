# -*- coding: utf-8 -*-
"""
Created on Fri Dec 27 15:58:13 2013

Esqueleto de agente usando los servicios web de Flask

/comm es la entrada para la recepcion de mensajes del agente
/Stop es la entrada que para el agente

Tiene una funcion AgentBehavior1 que se lanza como un thread concurrente

Asume que el agente de registro esta en el puerto 9000

@author: javier
"""

from __future__ import print_function
from multiprocessing import Process, Queue
import socket
import argparse
import random

from flask import Flask, render_template, request
from rdflib import Namespace, Graph,Literal,URIRef
from rdflib.namespace import FOAF, RDF
from flask import Flask, request

from AgentUtil.OntoNamespaces import ACL, DSO, AM2, RESTRICTION,MSG
from AgentUtil.ACLMessages import build_message, send_message, get_message_properties, directory_search_agent, register_message
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Agent import Agent
from AgentUtil.Logging import config_logger

__author__ = 'amazon2'

# Definimos los parametros de la linea de comandos
parser = argparse.ArgumentParser()
parser.add_argument('--open', help="Define si el servidor esta abierto al exterior o no", action='store_true',
                    default=False)
parser.add_argument('--port', type=int, help="Puerto de comunicacion del agente")
parser.add_argument('--dhost', default='localhost', help="Host del agente de directorio")
parser.add_argument('--dport', type=int, help="Puerto de comunicacion del agente de directorio")

# Logging
logger = config_logger(level=1)

# Configuration stuff
hostname = socket.gethostname()
port = 9040

# parsing de los parametros de la linea de comandos
args = parser.parse_args()

# Configuration stuff
if args.port is None:
    port = 9040
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

    # dhostname = socket.gethostname()
if args.dhost is None:
    dhostname = "localhost"
else:
    dhostname = args.dhost


agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0

# Datos del Agente

AgenteVendedorExterno = Agent('AgenteVendedorExterno',
                       agn.AgenteVendedorExterno,
                       'http://%s:%d/comm' % (hostname, port),
                       'http://%s:%d/Stop' % (hostname, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:9000/Register' % hostname,
                       'http://%s:9000/Stop' % hostname)


# Global triplestore graph
dsgraph = Graph()

cola1 = Queue()

# Flask stuff
app = Flask(__name__)

@app.route("/vende", methods=['GET', 'POST'])
def browser_vende():
    global mss_cnt
    """
    Permite la comunicacion con el agente via un navegador
    via un formulario
    """
    if request.method == 'GET':
        return render_template('ponerALaVenta.html', vendido = None)

    elif request.method == 'POST':
        # Hacer peticion de busqueda de productos con las restricciones del form
        if request.form['submit'] == 'Poner a la venta':
            return ponerALaVenta(request)
    
def ponerALaVenta(request):
    global mss_cnt

    gmess = Graph()

    sj_contenido = agn[AgenteVendedorExterno.name + 'Add_producto_externo_' + str(mss_cnt)]

    gmess.add((sj_contenido, RDF.type, AM2.Add_producto_externo))

    nombre = request.form['nombre']
    marca = request.form['marca']
    tipoProducto = request.form['tipoProducto']
    precio = request.form['precio']
    modelo = request.form['modelo']
    tipoEnvio = request.form['tipoEnvio']

    if nombre and marca and tipoProducto and precio and modelo and tipoEnvio:
        sujeto = AM2['Producto_externo_' + str(random.randint(0, 500000))]
        gmess.add((sujeto, RDF.type, AM2.Producto))
        gmess.add((sujeto, AM2.Nombre, Literal(nombre)))
        gmess.add((sujeto ,AM2.Marca, Literal(marca)))
        gmess.add((sujeto, AM2.TipoProducto, Literal(tipoProducto)))
        gmess.add((sujeto, AM2.Precio, Literal(precio)))
        gmess.add((sujeto, AM2.Modelo, Literal(modelo)))
        gmess.add((sujeto, AM2.TipoEnvio, Literal(tipoEnvio)))

        mostrador = directory_search_agent(DSO.AgenteProductosExternos,AgenteVendedorExterno,DirectoryAgent,mss_cnt)[0]
        msg = build_message(gmess, perf=ACL.request,
                sender=AgenteVendedorExterno.uri,
                receiver=mostrador.uri,
                content=sj_contenido,
                msgcnt=mss_cnt)
        puesto_a_la_venta = send_message(msg, mostrador.address)
        mss_cnt += 1

        logger.info('Recibimos respuesta a la peticion al servicio de informacion')
        return render_template('ponerALaVenta.html', vendido = puesto_a_la_venta)
    else:
        return render_template('ponerALaVenta.html', vendido = "Error")
    
    

    


@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicacion
    """
    global dsgraph
    global mss_cnt

    # Extraemos el mensaje y creamos un grafo con el
    message = request.args['content']
    gm = Graph()
    gm.parse(data=message)
    msgdic = get_message_properties(gm)
    mss_cnt += 1
    # Comprobamos que sea un mensaje FIPA ACL
    if msgdic is None:
        # Si no es, respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(), ACL['not-understood'], sender=AgenteVendedorExterno.uri, msgcnt=mss_cnt)

    else:
        # Obtenemos la performativa
        perf = msgdic['performative']
        if perf != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(), ACL['not-understood'], sender=AgenteVendedorExterno.uri, msgcnt=mss_cnt)

        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia de acciones del agente
            # de registro
            # Averiguamos el tipo de la accion
            if 'content' in msgdic:
                content = msgdic['content']
                accion = gm.value(subject=content, predicate=RDF.type)
                # Aqui realizariamos lo que pide la accion
                
                gr = build_message(Graph(), ACL['not-understood'], sender=AgenteVendedorExterno.uri, msgcnt=mss_cnt)

            else:
                gr = build_message(Graph(), ACL['not-understood'], sender=AgenteVendedorExterno.uri, msgcnt=mss_cnt)

    return gr.serialize(format='xml')




@app.route("/Stop")
def stop():
    """
    Entrypoint que para el agente

    :return:
    """
    tidyup()
    shutdown_server()
    return "Parando Servidor"


def tidyup():
    """
    Acciones previas a parar el agente
    """
    global cola1
    cola1.put(0)


def agentbehavior1(cola):
    """
    Un comportamiento del agente

    :return:
    """
    global mss_cnt
    logger.info('Nos registramos en el servicio de registro')
    register_message(DSO.AgenteVendedorExterno,AgenteVendedorExterno,DirectoryAgent,mss_cnt)
    fin = False
    # while not fin:
    #     while cola.empty():
    #         pass
    #     v = cola.get()
    #     if v == 0:
    #         fin = True
    #     else:
    #         print(v)


if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')


