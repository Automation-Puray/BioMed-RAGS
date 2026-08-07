<?php
header('Content-Type: application/json');
require 'db_connect.php';

// First, try to decode JSON data.
$data = json_decode(file_get_contents('php://input'), true);

// If JSON decoding fails, fallback to standard POST data.
if (empty($data)) {
    $data = $_POST;
}

$fiber_name = $data['fiber_name'] ?? null;
if (empty($fiber_name)) {
    echo json_encode(['error' => 'Fiber name is required.']);
    exit();
}
$manufacturer = $data['manufacturer'] ?? null;
$length_mm = $data['length_mm'] ?? null;
$core_diameter_um = $data['core_diameter_um'] ?? null;
$coatings = $data['coatings'] ?? null;
$material = $data['material'] ?? null;
$remarks = $data['remarks'] ?? null;

if (empty($fiber_name)) {
    echo json_encode(['error' => 'Fiber name is required.']);
    exit();
}

try {
    $stmt = $conn->prepare("
        INSERT INTO fibers (fiber_name, manufacturer, length_mm, core_diameter_um, coatings, material, remarks)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ");
    $stmt->bind_param("ssddsss", $fiber_name, $manufacturer, $length_mm, $core_diameter_um, $coatings, $material, $remarks);
    $stmt->execute();
    $fiber_id = $stmt->insert_id;
    $fiber_code = sprintf("F%04d", $fiber_id);
    $stmt->close();

    $update_stmt = $conn->prepare("UPDATE fibers SET fiber_code = ? WHERE fiber_id = ?");
    $update_stmt->bind_param("si", $fiber_code, $fiber_id);
    $update_stmt->execute();
    $update_stmt->close();

    echo json_encode(['fiber_id' => $fiber_id, 'fiber_code' => $fiber_code]);

} catch (mysqli_sql_exception $e) {
    http_response_code(500);
    echo json_encode(['error' => 'Database error: ' . $e->getMessage()]);
}

$conn->close();
