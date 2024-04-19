import yaml
import os
from pathlib import Path
import re

# Define input, output, and intermediate directories
input_folder = 'sourceDirectory'
output_folder = 'outputDirectory'
conversion_items_folder = 'workingDirectory'
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
    keys_to_remove = ['triggers', 'test', 'resources', 'status']
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


def modify_yaml(file_path, output_file_path):
    """
    Reads a YAML file and modifies its contents:
    1. Removes single quotes from Helm template expressions like '{{}}'.
    2. Replaces ${ENVIRONMENT} with {{ .Values.env }}.
    Saves the modified contents to a new file.
    """
    # Regular expression patterns
    quotes_pattern = re.compile(r"'{{.*?}}'")  # Matches single-quoted Helm template expressions
    env_pattern = re.compile(r'\${ENVIRONMENT}')  # Matches ${ENVIRONMENT} placeholder
    
    # Read the input file
    with open(file_path, 'r') as file:
        lines = file.readlines()
    
    # List to store modified lines
    modified_lines = []
    
    # Process each line
    for line in lines:
        # Remove single quotes from Helm template expressions
        modified_line = quotes_pattern.sub(lambda m: m.group(0).strip("'"), line)
        
        # Replace ${ENVIRONMENT} with {{ .Values.env }}
        modified_line = env_pattern.sub('{{ .Values.env }}', modified_line)
        
        # Append modified line to list
        modified_lines.append(modified_line)
    
    # Write the modified lines to the output file
    with open(output_file_path, 'w') as output_file:
        output_file.writelines(modified_lines)

def cleanup_yaml_files(directory_path):
    """
    Processes all YAML files in the specified directory.
    """
    # List all files in the directory
    files = os.listdir(directory_path)
    
    # Iterate through each file
    for file_name in files:
        # Check if the file is a YAML file
        if file_name.endswith('.yaml') or file_name.endswith('.yml'):
            # Construct the full file path
            file_path = os.path.join(directory_path, file_name)
            
            # Define the output file path (can be the same as input or different)
            output_file_path = file_path  # If you want to overwrite the input file
            
            # Modify the YAML file
            modify_yaml(file_path, output_file_path)




def process_file(input_file_path):
    """
    Process the given file by converting DeploymentConfig to Deployment.
    """
    try:
        # Load the YAML file
        with open(input_file_path, 'r') as file:
            hold_deploymentconfigs = list(yaml.load_all(file, Loader=yaml.SafeLoader))

            if 'objects' in hold_deploymentconfigs[0]:
                list_objects = hold_deploymentconfigs[0]['objects']
            else:
                list_objects = hold_deploymentconfigs


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
                                  print(f"Processing '{file_name}' DeploymentConfig...")
                              print("\n" + "=" * 80 + "\n")  # Separator for better readability

                              # Generate deployment files in helm chart
                              generate_helm_chart_deployment_data(contents, deploymentconfigname, output_folder, file_name)
                                  
                              
                      elif isinstance(contents, dict):
                          # Check if the 'kind' key is set to 'DeploymentConfig'
                          if contents.get('kind') == 'DeploymentConfig':
                              print()
                              print(f"Processing '{file_name}' DeploymentConfig...")
                              print("\n" + "=" * 80 + "\n")  # Separator for better readability

                              # Generate deployment files in helm chart
                              generate_helm_chart_deployment_data(contents, deploymentconfigname, output_folder, file_name)

                          if contents.get('kind') == 'Service':
                              servicename = contents['metadata']['name']
                              print()
                              print(f"Processing '{file_name}' Service...")
                              print("\n" + "=" * 80 + "\n")  # Separator for better readability

                              # Generate deployment files in helm chart
                              generate_helm_chart_service_data(contents, servicename, output_folder)

                          if contents.get('kind') == 'Route':
                              routename = contents['metadata']['name']
                              print(routename)
                              print()
                              print(f"Processing '{file_name}' Route...")
                              print("\n" + "=" * 80 + "\n")  # Separator for better readability

                              # Generate deployment files in helm chart
                              generate_helm_chart_route_data(contents, routename, output_folder)

                  except yaml.YAMLError as e:
                      print(f"Error parsing file '{file_name}': {e}")

    except Exception as e:
        print(f"Error processing file {input_file_path}: {e}")

def generate_helm_chart_route_data(data, b, o):
    if isinstance(data, dict):

        for key, value in data.items():
            # Replace hardcoded values with Helm template expressions
            # Example: Replace `replicas` with `{{ .Values.replicas }}`
            if key == 'name':
                data[key] = '{{ .Values.name }}'
            elif key == 'namespace':
                data[key] = '{{ .Release.Namespace }}'
            elif value == b:
                data[key] = '{{ .Values.name }}'

            elif key == 'app.kubernetes.io/part-of':
                data[key] = '{{ .Values.name }}'

            elif key == 'host':
                data[key] = "{{ .Values.route.name }}"


            elif key == 'annotations':
               data[key] = {}

            generate_helm_chart_route_data(value, b, o)

            helm_chart_directory = o + "/" + b
            templates_directory = os.path.join(helm_chart_directory, 'templates')
            output_route_path = os.path.join(templates_directory, f"{b}_routes.yaml") 
        
            with open(output_route_path, "w") as f:
                yaml.dump(data, f)  
                cleanup_yaml_files(templates_directory) 

    elif isinstance(data, list):
        for item in data:
            generate_helm_chart_route_data(item, b, o)

def generate_helm_chart_service_data(data, b, o):
    if isinstance(data, dict):

        for key, value in data.items():
            # Replace hardcoded values with Helm template expressions
            # Example: Replace `replicas` with `{{ .Values.replicas }}`

            # elif key == 'name':
            #     data[key] = '{{ .Values.name }}'
            if key == 'namespace':
                data[key] = '{{ .Release.Namespace }}'

            elif value == b:
                data[key] = '{{ .Values.name }}'

            elif key == 'app.kubernetes.io/part-of':
                data[key] = '{{ .Values.name }}'

            generate_helm_chart_service_data(value, b, o)
            helm_chart_directory = o + "/" + b
            templates_directory = os.path.join(helm_chart_directory, 'templates')
            output_svc_path = os.path.join(templates_directory, f"{b}_service.yaml") 
        
            with open(output_svc_path, "w") as f:
                yaml.dump(data, f)  
                cleanup_yaml_files(templates_directory) 

    elif isinstance(data, list):
        for item in data:
            generate_helm_chart_service_data(item, b, o)

    # helm_chart_directory = o + "/" + b
    # templates_directory = os.path.join(helm_chart_directory, 'templates')
    # output_svc_path = os.path.join(templates_directory, f"{b}_service.yaml") 

    # with open(output_svc_path, "w") as f:
    #     yaml.dump(data, f)  
    #     cleanup_yaml_files(templates_directory) 

def generate_helm_chart_deployment_data(a, b, o, fn):
    val = convert_deploymentconfig_to_deployment(a)
    helm_chart_directory = o + "/" + b
    templates_directory = os.path.join(helm_chart_directory, 'templates')
    chart_yaml_file = os.path.join(helm_chart_directory, 'Chart.yaml')
    values_yaml_file = os.path.join(helm_chart_directory, 'values.yaml')
                              
    # Create the Helm chart directory and subdirectories
    os.makedirs(templates_directory, exist_ok=True)
    chart_metadata = {
        'apiVersion': 'v2',
        'name': b,
        'description': 'A Helm chart for ' + b + ' application',
        'version': '0.1.0',
        'appVersion': '1.0.0'
    }
    #   env_pattern = re.compile(r'\${ENVIRONMENT}')
    matchLine = val['spec']['template']['spec']['containers'][0]['image'].split(":")
    mod = matchLine[0]+matchLine[1]
    values = {
                  'replicas': val['spec']['replicas'],
                  'name': val['metadata']['name'],
                  'env': 'dev', ## Placeholder. Update Values file for each environment
                  'repository': {
                      'image': mod, 
                      'tag': 'dev'                                               
                  },
                  'resources': {
                      'limits': {
                          'cpu': val['spec']['template']['spec']['containers'][0]['resources']['limits']['cpu'],
                          'memory': val['spec']['template']['spec']['containers'][0]['resources']['limits']['memory']
                      },
                      'requests': {
                          'cpu': val['spec']['template']['spec']['containers'][0]['resources']['requests']['cpu'],
                          'memory': val['spec']['template']['spec']['containers'][0]['resources']['requests']['memory']
                      }
                  }
              }
    #   env_pattern = re.compile(r'\${ENVIRONMENT}')
    matchLine = val['spec']['template']['spec']['containers'][0]['image'].split(":")
    mod = matchLine[0]+matchLine[1]
    values = {
                  'replicas': val['spec']['replicas'],
                  'name': val['metadata']['name'],
                  'env': 'dev', ## Placeholder. Update Values file for each environment
                  'route': {
                      'name': 'testname.placeholder.com',
                  },
                  'repository': {
                      'image': mod, 
                      'tag': 'dev'                                               
                  },
                  'resources': {
                      'limits': {
                          'cpu': val['spec']['template']['spec']['containers'][0]['resources']['limits']['cpu'],
                          'memory': val['spec']['template']['spec']['containers'][0]['resources']['limits']['memory']
                      },
                      'requests': {
                          'cpu': val['spec']['template']['spec']['containers'][0]['resources']['requests']['cpu'],
                          'memory': val['spec']['template']['spec']['containers'][0]['resources']['requests']['memory']
                      }
                  }
              }
    val['spec']['replicas'] = "{{ .Values.replicas }}"
    val['spec']['selector']['matchLabels']['app'] = "{{ .Values.name }}"
    val['spec']['template']['metadata']['labels']['app'] = "{{ .Values.name }}"
    val['spec']['template']['spec']['containers'][0]['image'] = "{{ .Values.repository.image }}"+":"+"{{ .Values.repository.tag}}"
    val['spec']['template']['spec']['containers'][0]['name'] = "{{ .Values.name }}"
    val['spec']['template']['spec']['containers'][0]['resources']['limits']['cpu'] = "{{ .Values.resources.limits.cpu }}"
    val['spec']['template']['spec']['containers'][0]['resources']['limits']['memory'] = "{{ .Values.resources.limits.memory }}"
    val['spec']['template']['spec']['containers'][0]['resources']['requests']['cpu'] = "{{ .Values.resources.requests.cpu }}"
    val['spec']['template']['spec']['containers'][0]['resources']['requests']['memory'] = "{{ .Values.resources.requests.memory }}"
    val['metadata']['namespace'] = "{{ .Release.Namespace }}"
    val['metadata']['name'] = "{{ .Values.name }}"
    
    with open(values_yaml_file, 'w') as file:
        yaml.dump(values, file, default_flow_style=False)

    # Write Chart.yaml
    with open(chart_yaml_file, 'w') as file:
        yaml.dump(chart_metadata, file, default_flow_style=False)

    # Write the modified manifests back to the YAML file in the deployment folder
    output_dc_path = os.path.join(templates_directory, f"{b}_deployment.yaml") 

    with open(output_dc_path, "w") as f:
        yaml.dump(val, f)  
    cleanup_yaml_files(templates_directory)     
    print(f"'{fn}' Deployment manifest generated!") 
    print()   
        

# Process all YAML files in the input folder
for file_name in os.listdir(input_folder):
    if file_name.endswith('.yaml') or file_name.endswith('.yml'):
        input_file_path = os.path.join(input_folder, file_name)
        process_file(input_file_path)
