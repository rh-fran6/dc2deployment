import yaml
import os
from pathlib import Path

# Define input, output, and intermediate directories
input_folder = 'deployment_config'
output_folder = 'deployment'
conversion_items_folder = 'conversion_items'
registry_url = 'my-image-registry.mydomain.com:5000'

# Ensure the output and intermediate folders exist; create them if not
os.makedirs(output_folder, exist_ok=True)
os.makedirs(conversion_items_folder, exist_ok=True)

def convert_deploymentconfig_to_deployment(manifest):
    """
    Converts DeploymentConfig manifest to Deployment manifest.
    """
    # Convert 'DeploymentConfig' to 'Deployment'
    manifest['kind'] = 'Deployment'
    manifest['apiVersion'] = 'apps/v1'

    # Set the strategy type to 'RollingUpdate'
    try:
        manifest['spec']['strategy']['type'] = 'RollingUpdate'
        # Remove rollingParams and activeDeadlineSeconds
        if 'rollingParams' in manifest['spec']['strategy']:
            del manifest['spec']['strategy']['rollingParams']
        if 'activeDeadlineSeconds' in manifest['spec']['strategy']:
            del manifest['spec']['strategy']['activeDeadlineSeconds']
    except KeyError:
        pass

    # Convert selector keys to matchLabels
    try:
        # Ensure matchLabels dictionary exists
        if 'matchLabels' not in manifest['spec']['selector']:
            manifest['spec']['selector']['matchLabels'] = {}

        # Copy key-value pairs from selector to matchLabels
        for key, value in manifest['spec']['selector'].items():
            if key != 'matchLabels':
                manifest['spec']['selector']['matchLabels'][key] = value

        # Remove the original keys from selector that are now in matchLabels
        keys_to_remove = [key for key in manifest['spec']['selector'] if key != 'matchLabels']
        for key in keys_to_remove:
            del manifest['spec']['selector'][key]
    except KeyError:
        print(f"Error handling matchLabels in manifest {manifest['metadata'].get('name')}, skipping.")

    # Check for triggers[0].imageChangeParams.from.name
    try:
        trigger = manifest['spec']['triggers'][0]
        image_change_params = trigger['imageChangeParams']
        image_name = image_change_params['from']['name']
        new_image_name = f"{registry_url}/{image_name}"

        # Use the value as the image name for the container
        manifest['spec']['template']['spec']['containers'][0]['image'] = new_image_name
    except (KeyError, IndexError):
        print(f"Error handling imageChangeParams in manifest {manifest['metadata'].get('name')}, skipping.")
    
    # Delete keys specific to DeploymentConfig
    keys_to_remove = ['triggers', 'test']
    for key in keys_to_remove:
        try:
            del manifest['spec'][key]
        except KeyError:
            pass

     # Delete strategy/resources specific to DeploymentConfig
    keys_to_remove = ['resources']
    for key in keys_to_remove:
        try:
            del manifest['spec']['strategy'][key]
        except KeyError:
            pass

     # Delete Status items from DeploymentConfig
    keys_to_remove = ['status']
    for key in keys_to_remove:
        try:
            del manifest[key]
        except KeyError:
            pass
    ## Return return of the parsing 
    return manifest

def process_file(input_file_path):
    """
    Process the given file by converting DeploymentConfig to Deployment.
    """
    try:
        # Load the YAML file
        with open(input_file_path, 'r') as file:
            hold_deploymentconfigs = list(yaml.load_all(file, Loader=yaml.SafeLoader))

            list_objects = hold_deploymentconfigs[0]['objects']

            ## If a template file, Extract different components
            for l in list_objects:                
                if l['kind'] == 'DeploymentConfig':
                    deploymentconfigname = l['metadata']['name']
                    deploymentconfigs = l
                    file_path_dc =  conversion_items_folder + '/' + deploymentconfigname + '_deploymentconfig.yaml'
                    with open(file_path_dc, 'w') as file:            
                       yaml.dump(deploymentconfigs, file)
                if l['kind'] == 'Service':
                    servicename = l['metadata']['name']
                    serviceconfig = l
                    file_path_svc =  conversion_items_folder + '/' + servicename + '_service.yaml'
                    with open(file_path_svc, 'w') as file:            
                       yaml.dump(serviceconfig, file)
                if l['kind'] == 'Route':
                    routename = l['metadata']['name']
                    routeconfig = l
                    file_path_route =  conversion_items_folder + '/' + routename + '_route.yaml'
                    with open(file_path_route, 'w') as file:            
                       yaml.dump(routeconfig, file)
                       
        for file_name in os.listdir(conversion_items_folder):
          # Construct the full file path
          file_path = os.path.join(conversion_items_folder, file_name)
      
          # Check if the file is a YAML file
          if file_name.endswith('.yaml') or file_name.endswith('.yml'):
              # Open the YAML file and load its contents
              with open(file_path, 'r') as file:
                  try:
                      contents = yaml.safe_load(file)
      
                      # Check if the contents are a list (for multiple YAML documents) or a dictionary
                      if isinstance(contents, list):
                          # Iterate through each document in the list
                          for document in contents:
                              # Check if the 'kind' key is set to 'DeploymentConfig'
                              if document.get('kind') == 'DeploymentConfig':
                                  print(f"The file '{file_name}' contains a document with kind 'DeploymentConfig'.")
                                  # Optionally, print the document
                                  print(document)
                                  convert_deploymentconfig_to_deployment(document)
                                  print("\n" + "=" * 80 + "\n")  # Separator for better readability
                      elif isinstance(contents, dict):
                          # Check if the 'kind' key is set to 'DeploymentConfig'
                          if contents.get('kind') == 'DeploymentConfig':
                              print(f"Processing '{file_name}' DeploymentConfig...")
                              # Optionally, print the document
                            #   print(contents)
                              val = convert_deploymentconfig_to_deployment(contents)

                              print("\n" + "=" * 80 + "\n")  # Separator for better readability
                              # Create the output file path in the deployment folder
                              output_file_path = os.path.join(output_folder, f"{deploymentconfigname}_deployment.yaml")                              
                              
                              # Write the modified manifests back to the YAML file in the deployment folder
                              with open(output_file_path, "w") as f:
                                  yaml.dump(val, f)  
                              print(f"'{file_name}' Deployment manifest ggenerated!")                    

                  except yaml.YAMLError as e:
                      print(f"Error parsing file '{file_name}': {e}")

    except Exception as e:
        print(f"Error processing file {input_file_path}: {e}")

# Process all YAML files in the input folder
for file_name in os.listdir(input_folder):
    if file_name.endswith('.yaml') or file_name.endswith('.yml'):
        input_file_path = os.path.join(input_folder, file_name)
        process_file(input_file_path)
