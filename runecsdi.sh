#!/bin/bash
echo "Running ECSDI Agents"
gnome-terminal -e "python ./src/Agentes/SimpleDirectoryService.py "
sleep 0.5
gnome-terminal -e "python ./src/Agentes/AgenteMostrarProductos.py"  --tab -e "python ./src/Agentes/AgenteLogistico.py" --tab -e  "python ./src/Agentes/AgenteVentaProductos.py" --tab -e  "python ./src/Agentes/AgenteCliente.py" --tab -e  "python ./src/Agentes/AgenteAlmacen.py" --tab -e  "python ./src/Agentes/AgenteTransportista1.py"  --tab -e  "python ./src/Agentes/AgenteTransportista2.py"
