#!/bin/bash
echo "Running ECSDI Agents"
gnome-terminal -e "python ./SimpleDirectoryService.py "
sleep 0.5
gnome-terminal -e "python ./AgenteLogistico.py" --tab -e  "python ./AgenteVentaProductos.py" --tab -e  "python ./AgenteCliente.py" --tab -e  "python ./AgenteAlmacen.py" --tab -e  "python ./AgenteProductosExternos.py"  --tab -e  "python ./AgenteVendedorExterno.py" --tab -e  "python ./AgenteTransportista.py --port 9031 --ntp 1 --precio 100 --contra 10" --tab -e  "python ./AgenteTransportista.py --port 9032 --ntp 2 --precio 200 --contra 0" --tab -e  "python ./AgenteTransportista.py --port 9033 --ntp 3 --precio 100 --contra 30" --tab -e "python ./AgenteMostrarProductos.py"  --tab -e "python ./AgenteRecomendador.py"  --tab 
