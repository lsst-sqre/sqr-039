"""Source for architecture.png, the architecture diagram."""

import os

from diagrams import Cluster, Diagram
from diagrams.gcp.compute import KubernetesEngine
from diagrams.gcp.database import SQL
from diagrams.gcp.network import LoadBalancing
from diagrams.gcp.storage import Filestore, PersistentDisk
from diagrams.onprem.client import User
from diagrams.onprem.compute import Server

os.chdir(os.path.dirname(__file__))

graph_attr = {
    "label": "",
}

with Diagram(
    "A&A",
    show=False,
    filename="architecture",
    outformat="png",
    graph_attr=graph_attr,
):
    user = User("End User")

    with Cluster("Science Platform"):
        filestore = Filestore("POSIX Filesystem")

        with Cluster("Authentication"):
            auth_ingress = LoadBalancing("NGINX Ingress")
            auth_server = KubernetesEngine("Server")
            storage = SQL("Metadata Store")
            redis = KubernetesEngine("Redis")
            redis_storage = PersistentDisk("Redis Storage")

            user >> auth_ingress >> auth_server >> redis >> redis_storage
            auth_server >> storage

        with Cluster("Notebook Aspect"):
            notebook_ingress = LoadBalancing("NGINX Ingress")
            hub = KubernetesEngine("Hub")
            session_storage = SQL("Session Storage")
            notebook = KubernetesEngine("Notebook")

            auth_server << notebook_ingress
            user >> notebook_ingress >> hub >> session_storage
            notebook_ingress >> notebook >> filestore
            notebook >> auth_server

        with Cluster("Portal Aspect"):
            portal_ingress = LoadBalancing("NGINX Ingress")
            portal = KubernetesEngine("Portal Aspect")

            auth_server << portal_ingress
            user >> portal_ingress >> portal

        with Cluster("API Services"):
            api_ingress = LoadBalancing("NGINX Ingress")
            api = KubernetesEngine("API Service")

            auth_server << api_ingress
            auth_server << api
            user >> api_ingress >> api
            notebook >> api
            portal >> api

        with Cluster("WebDAV"):
            webdav_ingress = LoadBalancing("NGINX Ingress")
            webdav_server = KubernetesEngine("Server")

            auth_server << webdav_ingress
            auth_server << webdav_server
            user >> webdav_ingress >> webdav_server >> filestore
            webdav_ingress << portal

    idp = Server("CILogon")

    auth_server >> idp
    user >> idp
