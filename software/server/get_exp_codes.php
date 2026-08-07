<?php
require_once 'db_connect.php';

header('Content-Type: application/json');

$fiber_code = $_GET['fiber_code'] ?? null;
$cath_code = $_GET['cath_code'] ?? null;

if (!$fiber_code) {
    echo json_encode([]);
    exit;
}

// Find the fiber_id based on the fiber_code
$stmt = $conn->prepare("SELECT fiber_id FROM fibers WHERE fiber_code = ?");
$stmt->bind_param("s", $fiber_code);
$stmt->execute();
$result = $stmt->get_result();
$fiber_data = $result->fetch_assoc();
$fiber_id = $fiber_data['fiber_id'];
$stmt->close();

if (!$fiber_id) {
    echo json_encode([]);
    exit;
}

$query = "SELECT exp_code FROM experiments WHERE fiber_id = ? AND img_ls_before_path IS NULL";
$params = "i";
$bind_values = [$fiber_id];

if ($cath_code) {
    // Find the cath_id based on the cath_code
    $stmt = $conn->prepare("SELECT cath_id FROM catheters WHERE cath_code = ?");
    $stmt->bind_param("s", $cath_code);
    $stmt->execute();
    $result = $stmt->get_result();
    $cath_data = $result->fetch_assoc();
    $cath_id = $cath_data['cath_id'];
    $stmt->close();
    
    // Check for a non-null cath_id in the experiments table
    $query .= " AND cath_id = ?";
    $params .= "i";
    $bind_values[] = $cath_id;
} else {
    // For a fiber-only experiment, cath_id should be NULL
    $query .= " AND cath_id IS NULL";
}

$query .= " ORDER BY exp_code DESC";

$stmt = $conn->prepare($query);
$stmt->bind_param($params, ...$bind_values);
$stmt->execute();
$result = $stmt->get_result();
$exp_codes = $result->fetch_all(MYSQLI_ASSOC);
$stmt->close();

$conn->close();

echo json_encode($exp_codes);
?>
