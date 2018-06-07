#!/bin/bash
echo "Running ECSDI Agents"
gnome-terminal -e "python ./SimpleDirectoryService.py "
sleep 0.5
gnome-terminal -e "python ./AgenteMostrarProductos.py"  --tab -e "python ./AgenteLogistico.py" --tab -e  "python ./AgenteVentaProductos.py" --tab -e  "python ./AgenteCliente.py" --tab -e  "python ./AgenteAlmacen.py" --tab -e  "python ./AgenteTransportista1.py"  --tab -e  "python ./AgenteTransportista2.py" --tab
