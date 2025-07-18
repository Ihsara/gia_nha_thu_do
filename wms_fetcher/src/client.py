import httpx
from owslib.wms import WebMapService

class WMSClient:
    """
    A client for interacting with Web Map Service (WMS) endpoints.
    """
    def __init__(self, service_url: str, version: str = '1.3.0'):
        """
        Initializes the WMS client.

        Args:
            service_url: The base URL of the WMS endpoint.
            version: The WMS version to use.
        """
        self.service_url = service_url
        self.wms = WebMapService(self.service_url, version=version)

    def get_layer_info(self, layer_name: str):
        """
        Retrieves information about a specific layer.

        Args:
            layer_name: The name of the layer.

        Returns:
            A dictionary containing layer details, or None if the layer is not found.
        """
        if layer_name in self.wms.contents:
            layer = self.wms.contents[layer_name]
            return {
                "title": layer.title,
                "abstract": layer.abstract,
                "bounding_box": layer.boundingBoxWGS84,
                "crs_options": layer.crsOptions,
                "styles": list(layer.styles.keys()),
            }
        return None

    def fetch_data(
        self,
        layer_name: str,
        bbox: tuple,
        srs: str,
        output_format: str,
        size: tuple = (1024, 1024),
    ):
        """
        Fetches data from a WMS layer for a given bounding box.

        Args:
            layer_name: The name of the layer to fetch data from.
            bbox: A tuple representing the bounding box (minx, miny, maxx, maxy).
            srs: The spatial reference system (e.g., 'EPSG:4326').
            output_format: The desired output format (e.g., 'application/json').
            size: The width and height of the output image.

        Returns:
            The raw data from the WMS response.
        """
        if layer_name not in self.wms.contents:
            raise ValueError(f"Layer '{layer_name}' not found in WMS capabilities.")

        try:
            response = self.wms.getfeatureinfo(
                layers=[layer_name],
                srs=srs,
                bbox=bbox,
                size=size,
                format=output_format,
                query_layers=[layer_name],
                info_format=output_format,
                xy=(size[0]//2, size[1]//2) # Query the center
            )
            return response.read()
        except httpx.HTTPStatusError as e:
            print(f"HTTP Error fetching data: {e}")
            return None
