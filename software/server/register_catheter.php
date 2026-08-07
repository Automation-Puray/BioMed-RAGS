<?php
header('Content-Type: application/json');
require 'db_connect.php';

$data = json_decode(file_get_contents('php://input'), true);

$cath_name = $data['cath_name'] ?? null;
if (empty($cath_name)) {
    echo json_encode(['error' => 'Catheter name is required.']);
    exit();
}
$model = $data['model'] ?? null;
$manufacturer = $data['manufacturer'] ?? null;
$material = $data['material'] ?? null;
$remarks = $data['remarks'] ?? null;

if (empty($cath_name)) {
    echo json_encode(['error' => 'Catheter name is required.']);
    exit();
}

try {
    $stmt = $conn->prepare("
        INSERT INTO catheters (cath_name, model, manufacturer, material, remarks)
        VALUES (?, ?, ?, ?, ?)
    ");
    $stmt->bind_param("sssss", $cath_name, $model, $manufacturer, $material, $remarks);
    $stmt->execute();
    $cath_id = $stmt->insert_id;
    $cath_code = sprintf("C%04d", $cath_id);
    $stmt->close();

    $update_stmt = $conn->prepare("UPDATE catheters SET cath_code = ? WHERE cath_id = ?");
    $update_stmt->bind_param("si", $cath_code, $cath_id);
    $update_stmt->execute();
    $update_stmt->close();

    echo json_encode(['cath_id' => $cath_id, 'cath_code' => $cath_code]);

} catch (mysqli_sql_exception $e) {
    http_response_code(500);
    echo json_encode(['error' => 'Database error: ' . $e->getMessage()]);
}

$conn->close();
?>
