<?php
header('Content-Type: application/json');
require 'db_connect.php';

$data = json_decode(file_get_contents('php://input'), true);

$fiber_id = $data['fiber_id'] ?? null;
$cath_id = $data['cath_id'] ?? null;

if (!$fiber_id) {
    echo json_encode(['error' => 'Fiber ID is required']);
    exit();
}

// 1. Get the last experiment ID for this fiber
$stmt = $conn->prepare("SELECT COUNT(*) AS exp_count FROM experiments WHERE fiber_id = ?");
$stmt->bind_param("i", $fiber_id);
$stmt->execute();
$result = $stmt->get_result();
$row = $result->fetch_assoc();
$new_exp_id = $row['exp_count'] + 1;

// 2. Generate the exp_code
$fiber_code_prefix = sprintf("F%04d", $fiber_id);
$cath_code_part = $cath_id !== null ? sprintf("_C%04d", $cath_id) : "";
$exp_code = sprintf("%s%s_E%04d", $fiber_code_prefix, $cath_code_part, $new_exp_id);

// 3. Insert the new experiment with the fiber-specific experiment ID and the new exp_code
$stmt = $conn->prepare("
    INSERT INTO experiments (fiber_id, cath_id, fiber_exp_id, exp_code)
    VALUES (?, ?, ?, ?)
");
$stmt->bind_param("iiis", $fiber_id, $cath_id, $new_exp_id, $exp_code);
$stmt->execute();

$inserted_exp_id = $stmt->insert_id; // Get the global auto-increment ID

// 4. Prepare the response with the desired formatting
echo json_encode([
    'exp_id' => $inserted_exp_id,
    'fiber_exp_id' => $new_exp_id,
    'exp_code' => $exp_code
]);
?>
