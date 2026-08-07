<?php
header('Content-Type: application/json');
require 'db_connect.php';

$result = $conn->query("SELECT cath_id, cath_code, cath_name, model, manufacturer, material, remarks FROM catheters ORDER BY cath_code");

if ($result) {
    $catheters = $result->fetch_all(MYSQLI_ASSOC);
    echo json_encode($catheters);
} else {
    // Return an empty array if the query fails or no catheters are found
    echo json_encode([]);
}

$conn->close();
?>
