# DeploymentConfig to Deployment Converter

This repository contains a Python script that converts `DeploymentConfig` manifests from OpenShift to `Deployment` manifests for Kubernetes. The script searches for manifests in a directory called `deployment_config`, converts them, and saves the converted files in a directory called `deployment`. It also maintains copies of the original files in a `conversion_items` directory.

## Prerequisites

- Python 3.x
- `pyyaml` library (can be installed using `pip install pyyaml`)

## Usage

1. **Clone the repository**:
    ```bash
    git clone https://github.com/rh-fran6/dc2deployment.git
    cd deployment-config-converter
    ```

2. **Prepare the `deployment_config` directory**:
    - Place the `DeploymentConfig` manifests you want to convert into the `deployment_config` directory.

3. **Run the script**:
    ```bash
    python convert_deployment_configs.py
    ```

4. **Check the output**:
    - The converted manifests will be saved in the `deployment` directory with filenames in the format `metadata.name_deployment.yaml`.
    - The original `DeploymentConfig` manifests are copied to the `conversion_items` directory with filenames in the format `metadata.name_deploymentconfig.yaml`.

## Error Handling

- The script includes error handling for potential issues such as file handling errors and manifest conversion problems.
- Any issues encountered during processing will be printed to the console.

## Contributing

We welcome contributions to this project. Please read the [CONTRIBUTING.md](CONTRIBUTING.md) file for guidelines on how to contribute.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Thanks for the efforts of [underguiz](https://gist.github.com/underguiz/3f61eed7942bfb221696be6019da0d22) which was heavily referred to.

## Contact

If you have any questions, suggestions, or feedback, please [open an issue](https://github.com/rh-fran6/dc2deployment/issues).

Happy converting!
