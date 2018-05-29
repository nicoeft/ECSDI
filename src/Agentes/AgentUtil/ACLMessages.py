# -*- coding: utf-8 -*-
"""
filename: ACLMessages

Utilidades para tratar los mensajes FIPA ACL

Created on 08/02/2014

@author: javier
"""
__author__ = 'javier'

from rdflib import Graph, Namespace, Literal
import requests
from rdflib.namespace import RDF, FOAF
from AgentUtil.OntoNamespaces import ACL ,DSO
from AgentUtil.Agent import Agent

agn = Namespace("http://www.agentes.org#")

def build_message(gmess, perf, sender=None, receiver=None,  content=None, msgcnt= 0):
    """
    Construye un mensaje como una performativa FIPA acl
    Asume que en el grafo que se recibe esta ya el contenido y esta ligado al
    URI en el parametro contenido

    :param gmess: grafo RDF sobre el que se deja el mensaje
    :param perf: performativa del mensaje
    :param sender: URI del sender
    :param receiver: URI del receiver
    :param content: URI que liga el contenido del mensaje
    :param msgcnt: numero de mensaje
    :return:
    """
    # Añade los elementos del speech act al grafo del mensaje
    mssid = 'message-'+str(sender.__hash__()) + '-{:{fill}4d}'.format(msgcnt, fill='0')
    ms = ACL[mssid]
    gmess.bind('acl', ACL)
    gmess.add((ms, RDF.type, ACL.FipaAclMessage))
    gmess.add((ms, ACL.performative, perf))
    gmess.add((ms, ACL.sender, sender))
    if receiver is not None:
        gmess.add((ms, ACL.receiver, receiver))
    if content is not None:
        gmess.add((ms, ACL.content, content))
    return gmess


def send_message(gmess, address):
    """
    Envia un mensaje usando un request y retorna la respuesta como
    un grafo RDF
    """
    msg = gmess.serialize(format='xml')
    r = requests.get(address, params={'content': msg})

    # Procesa la respuesta y la retorna como resultado como grafo
    gr = Graph()
    gr.parse(data=r.text)

    return gr


def get_message_properties(msg):
    """
    Extrae las propiedades de un mensaje ACL como un diccionario.
    Del contenido solo saca el primer objeto al que apunta la propiedad

    Los elementos que no estan, no aparecen en el diccionario
    """
    props = {'performative': ACL.performative, 'sender': ACL.sender,
             'receiver': ACL.receiver, 'ontology': ACL.ontology,
             'conversation-id': ACL['conversation-id'],
             'in-reply-to': ACL['in-reply-to'], 'content': ACL.content}
    msgdic = {} # Diccionario donde se guardan los elementos del mensaje

    # Extraemos la parte del FipaAclMessage del mensaje
    valid = msg.value(predicate=RDF.type, object=ACL.FipaAclMessage)

    # Extraemos las propiedades del mensaje
    if valid is not None:
        for key in props:
            val = msg.value(subject=valid, predicate=props[key])
            if val is not None:
                msgdic[key] = val
    return msgdic

def directory_search_agent(tipoDSO, origen,agenteDirectorio, mss_cnt):
    """
    Busca en el servicio de registro mandando un
    mensaje de request con una accion Search del servicio de directorio
    
    """

    gmess = Graph()

    gmess.bind('foaf', FOAF)
    gmess.bind('dso', DSO)
    reg_obj = agn[origen.name + '-search'] #nombre del graph -> AgenteCliente-search
    gmess.add((reg_obj, RDF.type, DSO.Search))  #añadimos el tipo de RDF-> Serach
    gmess.add((reg_obj, DSO.AgentType, tipoDSO)) #añadimos el tipo de agente que estamos pidiendo es el parm de la funcion (DSO.AgenteMostrarProductos)
    mss_cnt += 1
    msg = build_message(gmess, perf=ACL.request,
                        sender=origen.uri,
                        receiver=agenteDirectorio.uri,
                        content=reg_obj,
                        msgcnt=mss_cnt)
    gr = send_message(msg, agenteDirectorio.address)
    
    # Obtenemos la direccion del agente de la respuesta
    # No hacemos ninguna comprobacion sobre si es un mensaje valido
    msg = gr.value(predicate=RDF.type, object=ACL.FipaAclMessage) #Obtenemos el mensaje fipa 
    content = gr.value(subject=msg, predicate=ACL.content) #Obtenemos el contenido del mensaje fipa
    ragn_addr = gr.value(subject=content, predicate=DSO.Address) #Obtenemos la adress del contenido
    ragn_uri = gr.value(subject=content, predicate=DSO.Uri) #Obtenemos la uri del contenido
    name = gr.value(subject=content, predicate=FOAF.name) #Obtenemos el nombre del agente del contenido
    return Agent(name,ragn_uri,ragn_addr,None)


def register_message(tipoDSO,agenteRegistrar,agenteDirectorio,mss_cnt):
    """
    Envia un mensaje de registro al servicio de registro
    usando una performativa Request y una accion Register del
    servicio de directorio

    :param gmess:
    :return:
    """

    gmess = Graph()

    # Construimos el mensaje de registro
    gmess.bind('foaf', FOAF)
    gmess.bind('dso', DSO)
    reg_obj = agn[agenteRegistrar.name + '-Register']
    gmess.add((reg_obj, RDF.type, DSO.Register))
    gmess.add((reg_obj, DSO.Uri, agenteRegistrar.uri))
    gmess.add((reg_obj, FOAF.Name, Literal(agenteRegistrar.name)))
    gmess.add((reg_obj, DSO.Address, Literal(agenteRegistrar.address)))
    gmess.add((reg_obj, DSO.AgentType, tipoDSO))
    mss_cnt += 1
    # Lo metemos en un envoltorio FIPA-ACL y lo enviamos
    gr = send_message(
        build_message(gmess, perf=ACL.request,
                      sender=agenteRegistrar.uri,
                      receiver=agenteDirectorio.uri,
                      content=reg_obj,
                      msgcnt=mss_cnt),
        agenteDirectorio.address)
    

    return gr