<?php
// 1. Database connection setup
require_once 'db_connect.php'; // Make sure this file exists with your DB credentials

// 2. Check for a file upload
if (!isset($_FILES['hdf5_file']) || $_FILES['hdf5_file']['error'] !== UPLOAD_ERR_OK) {
    echo json_encode(['success' => false, 'message' => 'File upload failed or no file was sent.']);
    exit();
}

// 3. Get other POST data
$exp_id = (int)($_POST['exp_id'] ?? 0);
$fiber_id = (int)($_POST['fiber_id'] ?? 0);
$start_time = $_POST['start_time'] ?? null;
$end_time = $_POST['end_time'] ?? null;
// Validate IDs
if (!$exp_id || !$fiber_id) {
    echo json_encode(['success' => false, 'message' => 'Missing experiment or fiber ID.']);
    exit();
}

// 4. Set the destination directory and filename
// Make sure this directory exists and is writable on your server.
$uploadDir = 'hdf5_uploads/';
$fileName = $_FILES['hdf5_file']['name'];
$filePath = $uploadDir . $fileName;

// 5. Move the temporary file to the final destination
if (!move_uploaded_file($_FILES['hdf5_file']['tmp_name'], $filePath)) {
    echo json_encode(['success' => false, 'message' => 'Failed to save the uploaded file on the server. Check directory permissions.']);
    exit();
}

// 6. Update the database with the file path
$stmt = $conn->prepare("UPDATE experiments SET hdf5_path = ?, start_time = ?, end_time = ? WHERE exp_id = ? AND fiber_id = ?");
if ($stmt === false) {
    echo json_encode(['success' => false, 'message' => 'Database prepare failed: ' . $conn->error]);
    exit();
}

$stmt->bind_param("sssii", $filePath, $start_time, $end_time, $exp_id, $fiber_id);
if ($stmt->execute()) {
    echo json_encode(['success' => true, 'message' => 'File uploaded and path saved successfully.', 'path' => $filePath]);
} else {
    echo json_encode(['success' => false, 'message' => 'Failed to update database: ' . $stmt->error]);
}

$stmt->close();
$conn->close();
?>
