<?php
require_once 'db_connect.php';
 
// Define the base upload directory
$base_upload_dir = __DIR__ . '/uploads/';
/**
 * Handles a single file upload, moves it to the target directory, and returns the final path.
 *
 * @param array $file_info The $_FILES array for the specific file.
 * @param string $upload_dir The directory to move the file to.
 * @param string $new_filename The base name for the new file (without extension).
 * @return string|false The path to the uploaded file on success, false on failure.
 */
function uploadFile($file_info, $upload_dir, $new_filename) {
    if ($file_info['error'] === UPLOAD_ERR_OK) {
        $file_extension = pathinfo($file_info['name'], PATHINFO_EXTENSION);
        $final_filename = $new_filename . '.' . $file_extension;
        $upload_path = rtrim($upload_dir, '/') . '/' . $final_filename;

        // Check if the file already exists to prevent overwriting.
        if (file_exists($upload_path)) {
            // Optional: Handle existing files differently (e.g., append a number)
        }

        if (move_uploaded_file($file_info['tmp_name'], $upload_path)) {
            return $upload_path;
        }
    }
    return false;
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $timestamp = date('Ymd_His');
    // Trim and sanitize all incoming POST data
    $exp_code = trim($_POST['exp_code'] ?? '');
    $fiber_code = trim($_POST['fiber_code'] ?? '');
    $cath_code = trim($_POST['cath_code'] ?? '');

    // 1. A crucial validation step: verify that the exp_code exists and matches the selected fiber and cath codes
    $validation_query = "SELECT exp_id, fiber_id, cath_id FROM experiments WHERE exp_code = ?";
    $stmt = $conn->prepare($validation_query);
    if ($stmt === false) {
        die("Database error: Could not prepare validation query.");
    }
    $stmt->bind_param("s", $exp_code);
    $stmt->execute();
    $result = $stmt->get_result();
    $exp_data = $result->fetch_assoc();
    $stmt->close();

    if (!$exp_data) {
        die("Error: Invalid Experiment Code. Please select a valid code from the list.");
    }
    $exp_id = $exp_data['exp_id'];

    // 2. Validate Fiber and Cath codes against the fetched experiment data
    $fiber_query = "SELECT fiber_code FROM fibers WHERE fiber_id = ?";
    $stmt = $conn->prepare($fiber_query);
    $stmt->bind_param("i", $exp_data['fiber_id']);
    $stmt->execute();
    $result = $stmt->get_result();
    $db_fiber_row = $result->fetch_assoc();
    $db_fiber_code = $db_fiber_row['fiber_code'] ?? null;
    $stmt->close();

    $db_cath_code = null;
    if ($exp_data['cath_id'] !== null) {
        $cath_query = "SELECT cath_code FROM catheters WHERE cath_id = ?";
        $stmt = $conn->prepare($cath_query);
        $stmt->bind_param("i", $exp_data['cath_id']);
        $stmt->execute();
        $result = $stmt->get_result();
        $db_cath_row = $result->fetch_assoc();
        $db_cath_code = $db_cath_row['cath_code'] ?? null;
        $stmt->close();
    }
    $normalized_cath_code = empty($cath_code) ? null : $cath_code;
    if ($db_fiber_code !== $fiber_code || $db_cath_code !== $normalized_cath_code) {
        die("Error: The selected experiment code does not match the selected fiber/catheter. Please reload the form.");
    }

    // 3. Define the upload directory based on the experiment code
    $exp_dir = $base_upload_dir . $exp_code;
    if (!is_dir($exp_dir)) {
        mkdir($exp_dir, 0755, true);
    }

    // 4. Define mandatory files based on experiment type
    $mandatory_files = [
        'ls_before' => 'LS_end_before',
        'ls_after' => 'LS_end_after',
        'ldf_before' => 'LDF_end_before',
        'ldf_after' => 'LDF_end_after',
    ];
    if (!empty($cath_code)) {
        $mandatory_files['cath_before'] = 'Catheter_Before';
        $mandatory_files['cath_after'] = 'Catheter_After';
    }

    // 5. Upload mandatory files and collect paths
    $uploaded_paths = [];
    $update_failed = false;
    foreach ($mandatory_files as $field_name => $image_type) {
        // Check if the file was uploaded successfully and has no error
        if (isset($_FILES[$field_name]) && $_FILES[$field_name]['error'] === UPLOAD_ERR_OK) {
            $filename_base = $exp_code . '_' . $timestamp . '_' . $image_type;
            $uploaded_path = uploadFile($_FILES[$field_name], $exp_dir, $filename_base);
            if ($uploaded_path) {
                $uploaded_paths["img_{$field_name}_path"] = $uploaded_path;
            } else {
                echo "<h1>Upload Failed!</h1><p>Failed to move file for: " . htmlspecialchars($image_type) . ".</p>";
                $update_failed = true;
                break;
            }
        } else {
            // This is a required field, so a missing file is an error
            echo "<h1>Upload Failed!</h1><p>Missing or failed upload for: " . htmlspecialchars($image_type) . ".</p>";
            $update_failed = true;
            break;
        }
    }
    
    // 6. Only proceed with the database update if all mandatory files were uploaded
    if (!$update_failed) {
        // Build and execute the dynamic update query for mandatory fields
        $set_clauses = [];
        $bind_types = '';
        $bind_params = [];
        
        foreach ($uploaded_paths as $column_name => $path) {
            $set_clauses[] = "`{$column_name}` = ?";
            $bind_types .= 's';
            $bind_params[] = $path;
        }

        if (!empty($set_clauses)) {
            $bind_types .= 'i';
            $bind_params[] = $exp_id;
            
            $update_query = "UPDATE experiments SET " . implode(', ', $set_clauses) . " WHERE exp_id = ?";
            $stmt = $conn->prepare($update_query);
            $stmt->bind_param($bind_types, ...$bind_params);
            $stmt->execute();
            $stmt->close();
        }
        
        // 7. Handle "other" files
        if (isset($_FILES['others']) && is_array($_FILES['others']['tmp_name'])) {
            $insert_query = "INSERT INTO experiment_images (exp_id, image_name, path, description) VALUES (?, ?, ?, ?)";
            $stmt = $conn->prepare($insert_query);
            
            foreach ($_FILES['others']['tmp_name'] as $index => $tmp_name) {
                if ($_FILES['others']['error'][$index] === UPLOAD_ERR_OK) {
                    $description = $_POST['descriptions'][$index] ?? '';
                    $file_info = ['name' => $_FILES['others']['name'][$index], 'tmp_name' => $tmp_name, 'error' => UPLOAD_ERR_OK];
                    
                    $filename_base = $exp_code . '_' . $timestamp . '_other_' . ($index + 1);
                    $uploaded_path = uploadFile($file_info, $exp_dir, $filename_base);

                    if ($uploaded_path) {
                        $filename = $filename_base . '.' . pathinfo($_FILES['others']['name'][$index], PATHINFO_EXTENSION);
                        $stmt->bind_param("isss", $exp_id, $filename, $uploaded_path, $description);
                        $stmt->execute();
                    }
                }
            }
            $stmt->close();
        }
        
        // Final success message
        echo "<h1>Upload Successful! ✅</h1>";
        echo "<p>Photos for Experiment Code: <strong>" . htmlspecialchars($exp_code) . "</strong> have been saved.</p>";
        echo "<a href='upload_form.php'>Upload more photos</a>";

        $conn->close();
    }
} else {
    // If not a POST request, redirect back to the form
    header('Location: upload_form.php');
    exit();
}
?>
