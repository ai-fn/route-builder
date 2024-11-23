import os
import folium
import logging
import requests
import numpy as np

from numpy.typing import NDArray
from typing import Dict, List, Tuple, Optional
from scipy.optimize import linear_sum_assignment

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


class RouteBuilder:
    """
    A class to build and visualize optimized delivery routes based on geographic locations.

    Attributes:
        locations (Dict[str, Tuple[float, float]]):
            A dictionary containing location names as keys and their coordinates (latitude, longitude) as values.
    """

    def __init__(self, locations: Dict[str, Tuple[float, float]]) -> None:
        """
        Initialize the RouteBuilder with the given locations.

        Args:
            locations (Dict[str, Tuple[float, float]]): A dictionary of locations.
        """
        self.locations = locations

    def build(self, filename: Optional[str] = "optimized_route.html") -> None:
        """
        Build and save the optimized route as an HTML file.

        Args:
            filename (Optional[str]): The name of the output HTML file. Defaults to "optimized_route.html".
        """
        target_ext = ".html"
        _, ext = os.path.splitext(filename)
        if ext != target_ext:
            logger.warning(
                f"The filename extension should be '{target_ext}', provided '{ext}'."
            )

        distance_matrix = self._get_distance_matrix(self.locations)
        route_order = self._optimize_route_scipy(distance_matrix)

        ordered_locations = [list(self.locations.values())[i] for i in route_order]
        route_coordinates = self._get_route_via_osrm(ordered_locations)
        route_map = self._visualize_route(route_coordinates)

        route_map.save(filename)
        logger.info(f"The route is saved to a file '{filename}'.")

    def _visualize_route(
        self, route_coordinates: List[Tuple[float, float]]
    ) -> folium.Map:
        """
        Visualize the optimized route on a map.

        Args:
            route_coordinates (List[Tuple[float, float]]): List of route coordinates obtained from OSRM.

        Returns:
            folium.Map: A map object with the visualized route and markers.
        """
        m = folium.Map(location=list(self.locations["warehouse"]), zoom_start=4)

        folium.PolyLine(
            [(lat, lng) for lng, lat in route_coordinates], color="blue", weight=2.5
        ).add_to(m)

        for name, coords in self.locations.items():
            folium.Marker(location=coords, tooltip=name).add_to(m)

        return m

    def _get_route_via_osrm(
        self, ordered_locations: List[Tuple[float, float]]
    ) -> List[List[float]]:
        """
        Obtain route geometry from OSRM.

        Args:
            ordered_locations (List[Tuple[float, float]]): A list of ordered locations (latitude, longitude).

        Returns:
            List[List[float]]: A list of coordinates representing the route.
        """
        base_url = "http://router.project-osrm.org/route/v1/driving/"
        coordinates = ";".join([f"{lng},{lat}" for lat, lng in ordered_locations])
        url = f"{base_url}{coordinates}?overview=full&geometries=geojson"

        response = requests.get(url)
        if response.status_code != 200:
            raise Exception("Failed to obtain a route from OSRM")

        data = response.json()
        return data["routes"][0]["geometry"]["coordinates"]

    def _get_distance_matrix(
        self, locations: Dict[str, Tuple[float, float]]
    ) -> NDArray:
        """
        Obtain a distance matrix using OSRM API.

        Args:
            locations (Dict[str, Tuple[float, float]]): A dictionary of locations.

        Returns:
            NDArray: A 2D array representing distances between all locations.
        """
        base_url = "http://router.project-osrm.org/table/v1/driving/"
        coordinates = ";".join([f"{lng},{lat}" for lat, lng in locations.values()])
        url = f"{base_url}{coordinates}?annotations=distance"

        response = requests.get(url)
        if response.status_code != 200:
            raise Exception("Failed to obtain distance matrix from OSRM")

        data = response.json()
        return np.array(data["distances"])

    def _optimize_route_scipy(self, distance_matrix: NDArray) -> List[int]:
        """
        Optimize the route using SciPy's linear sum assignment method.

        Args:
            distance_matrix (NDArray): A 2D array of distances between locations.

        Returns:
            List[int]: A list of indices representing the optimized route order.
        """
        row_ind, col_ind = linear_sum_assignment(distance_matrix)
        return [row_ind[i] for i in col_ind]
