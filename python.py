import yaml
import os
import shutil
import sys

# Define input, output, and intermediate directories
input_folder = 'deployment_config'
output_folder = 'deployment'
conversion_items_folder = 'conversion_items'
registry_url = 'default-route-openshift-image-registry.mydomain.com:5000'

# Ensure the output and intermediate folders exist; create them if not
os.makedirs(output_folder, exist_ok=True)
os.makedirs(conversion_items_folder, exist_ok=True)

# Process all YAML files in the input folder
for file_name in os.listdir(input_folder):
    # Check if the file is a YAML file
    if file_name.endswith('.yaml') or file_name.endswith('.yml'):
        input_file_path = os.path.join(input_folder, file_name)
        
        try:
            # Load the YAML file
            with open(input_file_path, 'r') as file:
                deploymentconfigs = list(yaml.load_all(file, Loader=yaml.SafeLoader))
            
            # Remove any None value at the end of the deploymentconfig list
            if deploymentconfigs and deploymentconfigs[-1] is None:
                del deploymentconfigs[-1]

            # Copy the original file to the conversion_items folder
            shutil.copy(input_file_path, conversion_items_folder)
            # Rename the copied file based on the metadata.name property
            if deploymentconfigs:
                metadata_name = deploymentconfigs[0].get('metadata', {}).get('name')
                if metadata_name:
                    new_file_name = f"{metadata_name}_deploymentconfig.yaml"
                    shutil.move(os.path.join(conversion_items_folder, file_name), 
                                os.path.join(conversion_items_folder, new_file_name))

            # Process each manifest and convert it
            for manifest in deploymentconfigs:
                if manifest and manifest['kind'] == 'DeploymentConfig':
                    # Get the metadata name
                    metadata_name = manifest.get('metadata', {}).get('name')

                    # Convert 'DeploymentConfig' to 'Deployment'
                    manifest['kind'] = 'Deployment'
                    manifest['apiVersion'] = 'apps/v1'

                    # Set the strategy type to 'RollingUpdate'
                    try:
                        manifest['spec']['strategy']['type'] = 'RollingUpdate'
                    except KeyError:
                        pass        

                    # Convert selector keys to matchLabels
                    try:
                        # Ensure matchLabels dictionary exists
                        if 'matchLabels' not in manifest['spec']['selector']:
                            manifest['spec']['selector']['matchLabels'] = {}
                    
                        # Copy key-value pairs from selector to matchLabels
                        # Update matchLabels directly with the items from selector
                        for key, value in manifest['spec']['selector'].items():
                            if key != 'matchLabels':
                                manifest['spec']['selector']['matchLabels'][key] = value
                    
                        # Remove the original keys from selector that are now in matchLabels
                        # This way, matchLabels will only contain the key-value pairs
                        keys_to_remove = [key for key in manifest['spec']['selector'] if key != 'matchLabels']
                        for key in keys_to_remove:
                            del manifest['spec']['selector'][key]

                    except KeyError:
                        print(f"Error handling matchLabels in manifest {metadata_name}, skipping.")
                    
                    # Delete 'rollingParams' and its sub-keys from 'spec['strategy']'
                    try:
                        del manifest['spec']['strategy']['rollingParams']
                    except KeyError:
                        pass

                    # Delete 'activeDeadlineSeconds' from 'spec['strategy']['activeDeadlineSeconds']
                    try:
                        del manifest['spec']['strategy']['activeDeadlineSeconds']
                    except KeyError:
                        pass

                    # Check for triggers[0].imageChangeParams.from.name
                    try:
                        trigger = manifest['spec']['triggers'][0]
                        image_change_params = trigger['imageChangeParams']
                        image_name = image_change_params['from']['name']
                        new_image_name = f"{registry_url}/{image_name}"

                        # Use the value as the image name for the container
                        manifest['spec']['template']['spec']['containers'][0]['image'] = new_image_name

                    except (KeyError, IndexError):
                        print(f"Error handling imageChangeParams in manifest {metadata_name}, skipping.")

                    # Delete other keys in the manifest as per the original script
                    for key in ['triggers', 'test', 'strategy/activeDeadlineSeconds', 'strategy/resources']:
                        try:
                            del manifest['spec'][key]
                        except KeyError:
                            pass
                    
                    # Create the output file path in the deployment folder
                    output_file_path = os.path.join(output_folder, f"{metadata_name}_deployment.yaml")
                    
                    # Write the modified manifests back to the YAML file in the deployment folder
                    with open(output_file_path, "w") as deployment:
                        yaml.dump_all(deploymentconfigs, deployment, default_flow_style=False)

        except Exception as e:
            print(f"Error processing file {input_file_path}: {e}")
