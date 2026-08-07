<?php
header('Content-Type: application/json');
require 'db_connect.php';

$result = $conn->query("SELECT fiber_id, fiber_code, fiber_name, manufacturer, length_mm, core_diameter_um, coatings, material, remarks FROM fibers ORDER BY fiber_code");

if ($result) {
    $fibers = $result->fetch_all(MYSQLI_ASSOC);
    echo json_encode($fibers);
} else {
    echo json_encode([]);
}

$conn->close();
