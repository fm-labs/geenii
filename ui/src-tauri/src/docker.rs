use serde::{Deserialize, Serialize};

// Docker info response structure
#[derive(Serialize, Deserialize, Debug)]
pub struct DockerInfo {
    pub success: bool,
    pub output: Option<String>,
    pub error: Option<String>,
    //pub parsed_info: Option<DockerSystemInfo>,
}

// pub async fn docker_check_availability() -> Result<bool, String> {
//     tokio::task::spawn_blocking(|| {
//         let output = Command::new("docker")
//             .arg("version")
//             .arg("--format")
//             .arg("{{.Server.Version}}")
//             .output();
//
//         match output {
//             Ok(output) => Ok(output.status.success()),
//             Err(_) => Ok(false),
//         }
//     })
//     .await
//     .map_err(|e| format!("Task execution failed: {}", e))
// }
//
// // Basic docker info command
// pub async fn docker_info() -> Result<DockerInfo, String> {
//     tokio::task::spawn_blocking(|| {
//         let output = Command::new("docker")
//             .arg("info")
//             .arg("--format")
//             .arg("{{json .}}")
//             .output();
//
//         match output {
//             Ok(output) => {
//                 if output.status.success() {
//                     let stdout = String::from_utf8_lossy(&output.stdout).to_string();
//                     //let parsed_info = parse_docker_info(&stdout);
//
//                     Ok(DockerInfo {
//                         success: true,
//                         output: Some(stdout),
//                         error: None,
//                         //parsed_info,
//                     })
//                 } else {
//                     let stderr = String::from_utf8_lossy(&output.stderr).to_string();
//                     Ok(DockerInfo {
//                         success: false,
//                         output: None,
//                         error: Some(stderr),
//                         //parsed_info: None,
//                     })
//                 }
//             }
//             Err(e) => Ok(DockerInfo {
//                 success: false,
//                 output: None,
//                 error: Some(format!("Failed to execute docker command: {}", e)),
//                 //parsed_info: None,
//             }),
//         }
//     })
//     .await
//     .map_err(|e| format!("Task execution failed: {}", e))?
// }
