<?php
// Include the database connection script
require_once 'db_connect.php';

// Fetch fiber codes and catheter codes
$fiber_query = "SELECT fiber_id, fiber_code FROM fibers ORDER BY fiber_code";
$fiber_result = $conn->query($fiber_query);
$fibers = $fiber_result->fetch_all(MYSQLI_ASSOC);

$cath_query = "SELECT cath_id, cath_code FROM catheters ORDER BY cath_code";
$cath_result = $conn->query($cath_query);
$catheters = $cath_result->fetch_all(MYSQLI_ASSOC);

$conn->close();
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Experiment Photo Documentation</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; }
        .form-container { max-width: 600px; margin: auto; padding: 20px; border: 1px solid #ccc; border-radius: 5px; }
        label, select, input, button { display: block; margin-bottom: 10px; width: 100%; box-sizing: border-box; }
        .file-group { margin-bottom: 20px; padding: 10px; border: 1px dashed #ccc; }
    </style>
</head>
<body>

<div class="form-container">
    <h2>Experiment Photo Documentation</h2>
    <form action="process_upload.php" method="post" enctype="multipart/form-data">

        <label for="fiber_code">Fiber Code:</label>
        <select id="fiber_code" name="fiber_code" required>
            <option value="">-- Select a Fiber --</option>
            <?php foreach ($fibers as $fiber): ?>
                <option value="<?php echo htmlspecialchars($fiber['fiber_code']); ?>">
                    <?php echo htmlspecialchars($fiber['fiber_code']); ?>
                </option>
            <?php endforeach; ?>
        </select>

        <label for="cath_code">Catheter Code (Optional):</label>
        <select id="cath_code" name="cath_code">
            <option value="">-- No Catheter --</option>
            <?php foreach ($catheters as $catheter): ?>
                <option value="<?php echo htmlspecialchars($catheter['cath_code']); ?>">
                    <?php echo htmlspecialchars($catheter['cath_code']); ?>
                </option>
            <?php endforeach; ?>
        </select>

        <label for="exp_code">Experiment Code:</label>
        <select id="exp_code" name="exp_code" required>
            <option value="">-- Select an Experiment --</option>
        </select>

        <hr>

        <h3>Mandatory Photos</h3>
        <p>Please upload the required images for this experiment.</p>
        <div class="file-group">
            <label for="ls_before">LS End Before:</label>
            <input type="file" id="ls_before" name="ls_before" required>

            <label for="ls_after">LS End After:</label>
            <input type="file" id="ls_after" name="ls_after" required>

            <label for="ldf_before">LDF End Before:</label>
            <input type="file" id="ldf_before" name="ldf_before" required>

            <label for="ldf_after">LDF End After:</label>
            <input type="file" id="ldf_after" name="ldf_after" required>

            <div id="cath-photos" style="display: none;">
                <label for="cath_before">Catheter Before:</label>
                <input type="file" id="cath_before" name="cath_before">
                <label for="cath_after">Catheter After:</label>
                <input type="file" id="cath_after" name="cath_after">
            </div>
        </div>

        <h3>Other Observations</h3>
        <div id="other-uploads-container">
            <div class="file-group other-upload-group">
                <label for="other_1">Other Photo 1:</label>
                <input type="file" id="other_1" name="others[]">
                <label for="desc_1">Description:</label>
                <input type="text" id="desc_1" name="descriptions[]">
            </div>
        </div>
        <button type="button" onclick="addMore()">+ Add More Photos</button>
        
        <br>
        <br>
        <button type="submit">Upload Photos</button>

    </form>
</div>


<script>
    function updateExperimentCodes() {
        const fiberCode = document.getElementById('fiber_code').value;
        const cathCode = document.getElementById('cath_code').value;
        const expCodeSelect = document.getElementById('exp_code');
        const cathPhotosDiv = document.getElementById('cath-photos');
        
        // Show/hide catheter photo fields
        if (cathCode) {
            cathPhotosDiv.style.display = 'block';
        } else {
            cathPhotosDiv.style.display = 'none';
        }

        // --- THE FIX ---
        // Always reset the experiment code dropdown to a loading state.
        expCodeSelect.innerHTML = '<option value="">-- Loading... --</option>';

        // If no fiber code is selected, stop here and reset to default
        if (!fiberCode) {
            expCodeSelect.innerHTML = '<option value="">-- Select an Experiment --</option>';
            return;
        }

        // Fetch new experiment codes
        const url = `get_exp_codes.php?fiber_code=${fiberCode}&cath_code=${cathCode}`;
        fetch(url)
            .then(response => response.json())
            .then(data => {
                expCodeSelect.innerHTML = '<option value="">-- Select an Experiment --</option>';
                data.forEach(exp => {
                    const option = document.createElement('option');
                    option.value = exp.exp_code;
                    option.textContent = exp.exp_code;
                    expCodeSelect.appendChild(option);
                });
            })
            .catch(error => {
                console.error('Error fetching experiment codes:', error);
                expCodeSelect.innerHTML = '<option value="">-- Error loading codes --</option>';
            });
    }

    document.getElementById('fiber_code').addEventListener('change', updateExperimentCodes);
    document.getElementById('cath_code').addEventListener('change', updateExperimentCodes);

    // Initial load
    updateExperimentCodes();

    let otherCount = 1;
    function addMore() {
        otherCount++;
        const container = document.getElementById('other-uploads-container');
        const newGroup = document.createElement('div');
        newGroup.className = 'file-group other-upload-group';
        newGroup.innerHTML = `
            <label for="other_${otherCount}">Other Photo ${otherCount}:</label>
            <input type="file" id="other_${otherCount}" name="others[]">
            <label for="desc_${otherCount}">Description:</label>
            <input type="text" id="desc_${otherCount}" name="descriptions[]">
        `;
        container.appendChild(newGroup);
    }
</script>
