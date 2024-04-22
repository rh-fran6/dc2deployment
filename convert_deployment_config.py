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

def convert_deploymentconfig_to_deployment(data, app_name):

    # Convert 'DeploymentConfig' to 'Deployment'
    data['kind'] = 'Deployment'
    data['apiVersion'] = 'apps/v1'

    try:
        data['spec']['strategy']['type'] = 'RollingUpdate'
        if 'rollingParams' in data['spec']['strategy']:
            del data['spec']['strategy']['rollingParams']
        if 'activeDeadlineSeconds' in data['spec']['strategy']:
            del data['spec']['strategy']['activeDeadlineSeconds']
    except KeyError:
        pass

    try:
        if 'matchLabels' not in data['spec']['selector']:
            data['spec']['selector']['matchLabels'] = {}

        for key, value in data['spec']['selector'].items():
            if key != 'matchLabels':
                data['spec']['selector']['matchLabels'][key] = value

        keys_to_remove = [key for key in data['spec']['selector'] if key != 'matchLabels']
        for key in keys_to_remove:
            del data['spec']['selector'][key]

    except KeyError:
        print(f"Error handling matchLabels in manifest {data['metadata'].get('name')}, skipping.")

    try:
        for k in data['spec']['triggers']:
            if 'imageChangeParams' in k:
                new_image_name = registry_url + '/' + k['imageChangeParams']['from']['name']
                data['spec']['template']['spec']['containers'][0]['image'] = new_image_name

    except (KeyError, IndexError):
        print(f"Error handling imageChangeParams in manifest {data['metadata'].get('name')}, skipping.")

    keys_to_remove = ['triggers', 'test', 'resources', 'status']
    for key in keys_to_remove:
        try:
            del data['spec'][key]
        except KeyError:
            pass

    keys_to_remove = ['resources']
    for key in keys_to_remove:
        try:
            del data['spec']['strategy'][key]
        except KeyError:
            pass

    keys_to_remove = ['status']
    for key in keys_to_remove:
        try:
            del data[key]
        except KeyError:
            pass

    return data


def modify_yaml(file_path, output_file_path):
    """
    Reads a YAML file and modifies its contents:
    1. Removes single quotes from Helm template expressions like '{{}}'.
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
                app_name = list_objects[0]['metadata']['name'] 
            else:
                list_objects = hold_deploymentconfigs
                app_name = list_objects[0]['metadata']['name'] 

            ## Generate Helm Chart boiler plate
                
            generate_helm_chart_boilerplate(app_name)          


            ## If a template file, Extract different components
            for l in list_objects:             
                if l['kind'] == 'DeploymentConfig':
                    file_path_dc =  conversion_items_folder + '/' + app_name + '_deploymentconfig.yaml'
                    with open(file_path_dc, 'w') as file:            
                       yaml.dump(l, file)               
                    print(app_name + " deploymentconfig done... ")
                    print()
                    generate_helm_chart_deployment_data(l, app_name)

                if l['kind'] == 'Service':
                    file_path_svc =  conversion_items_folder + '/' + app_name + '_service.yaml'
                    with open(file_path_svc, 'w') as file:            
                       yaml.dump(l, file)
                    print(app_name + " service done... ")
                    print()
                    update_service_helm_values(l, app_name)

                if l['kind'] == 'Route':
                    file_path_route =  conversion_items_folder + '/' + app_name + '_route.yaml'
                    with open(file_path_route, 'w') as file:            
                       yaml.dump(l, file)
                    print( app_name + " route done... ")
                    print()
                    update_route_helm_values(l, app_name)

                if l['kind'] == 'CronJob':
                    file_path_cronjob =  conversion_items_folder + '/' + app_name + '_cronjob.yaml'
                    with open(file_path_cronjob, 'w') as file:            
                       yaml.dump(l, file)
                    print(app_name + " cronjob done... ")
                    print()

    except Exception as e:
        print(f"Error processing file {input_file_path}: {e}")

def generate_helm_chart_resources (data, app_name, resourceType):
    helm_output_resource_path = output_folder + '/' + app_name + '/' + 'templates' + '/' + f'{app_name}_{resourceType}.yaml'
    helm_templates_directory = output_folder + '/' + app_name + '/' + 'templates'

    # Dump YAML data to the file
    with open(helm_output_resource_path, 'w') as file:
        yaml.dump(data, file)
    cleanup_yaml_files(helm_templates_directory) 


def update_route_helm_values(data, app_name):  

    for key, value in data.items():
        if isinstance(value, dict):
            update_route_helm_values(value, app_name)
        else:
            if key == 'name':
                data[key] = '{{ .Values.name }}'

            elif key == 'namespace':
                data[key] = '{{ .Release.Namespace }}'

            elif value == app_name:
                data[key] = '{{ .Values.name }}'

            elif key == 'app.kubernetes.io/part-of':
                data[key] = '{{ .Values.name }}'

            elif key == 'host':
                data[key] = "{{ .Values.route.name }}"

            elif key == 'annotations':
               data[key] = {}

    generate_helm_chart_resources(data, app_name, 'route' )

def update_service_helm_values (data, app_name): 

    for key, value in data.items():
        if isinstance(value, dict):
            update_route_helm_values(value, app_name)
        else:
            if key == 'name':
                data[key] = '{{ .Values.name }}'
                
            elif key == 'namespace':
                data[key] = '{{ .Release.Namespace }}'

            elif value == app_name:
                data[key] = '{{ .Values.name }}'

            elif key == 'app.kubernetes.io/part-of':
                data[key] = '{{ .Values.name }}'

            elif key == 'host':
                data[key] = "{{ .Values.route.name }}"

            elif key == 'annotations':
               data[key] = {}
    generate_helm_chart_resources(data, app_name, 'service' )

def generate_helm_chart_boilerplate (app_name):
    helm_chart_directory = output_folder + "/" + app_name
    templates_directory = os.path.join(helm_chart_directory, 'templates')
    chart_yaml_file = os.path.join(helm_chart_directory, 'Chart.yaml')
    os.makedirs(templates_directory, exist_ok=True)
    chart_metadata = {
        'apiVersion': 'v2',
        'name': app_name,
        'description': 'A Helm chart for ' + app_name + ' application',
        'version': '0.1.0',
        'appVersion': '1.0.0'
    }
    with open(chart_yaml_file, 'w') as file:
        yaml.dump(chart_metadata, file, default_flow_style=False)
        

def generate_helm_chart_deployment_data(data, app_name):
    val = convert_deploymentconfig_to_deployment(data, app_name)
    helm_chart_directory = output_folder + "/" + app_name
    templates_directory = os.path.join(helm_chart_directory, 'templates')
    values_yaml_file = os.path.join(helm_chart_directory, 'values.yaml')

    matchLine = val['spec']['template']['spec']['containers'][0]['image'].split(":")
    mod = matchLine[0]+matchLine[1]
    values = {
           'replicas': val['spec']['replicas'],
           'name': val['metadata']['name'],
           'env': 'dev',  # Placeholder. Update Values file for each environment
           'route': {
               'name': 'testname.placeholder.com',
           },
           'resources': {},
           'repository': {
               'image': mod,
               'tag': 'dev'
           }
       }
       
    container = val['spec']['template']['spec']['containers'][0]
    
    if 'resources' in container:
        container_resources = container['resources']
        
        if 'limits' in container_resources:
            res1 = {
                    'limits': {
                        'cpu': val['spec']['template']['spec']['containers'][0]['resources']['limits']['cpu'],
                        'memory': val['spec']['template']['spec']['containers'][0]['resources']['limits']['memory']
                    }
                }
            values['resources'].update(res1)
            val['spec']['template']['spec']['containers'][0]['resources']['limits']['cpu'] = "{{ .Values.resources.limits.cpu }}"
            val['spec']['template']['spec']['containers'][0]['resources']['limits']['memory'] = "{{ .Values.resources.limits.memory }}"
    
        if 'requests' in container_resources:
            res1 = {
                    'requests': {
                        'cpu': val['spec']['template']['spec']['containers'][0]['resources']['requests']['cpu'],
                        'memory': val['spec']['template']['spec']['containers'][0]['resources']['requests']['memory']
                    }
                }
            values['resources'].update(res1)
            val['spec']['template']['spec']['containers'][0]['resources']['requests']['cpu'] = "{{ .Values.resources.requests.cpu }}"
            val['spec']['template']['spec']['containers'][0]['resources']['requests']['memory'] = "{{ .Values.resources.requests.memory }}"

    val['spec']['replicas'] = "{{ .Values.replicas }}"
    val['spec']['selector']['matchLabels']['app'] = "{{ .Values.name }}"
    val['spec']['template']['metadata']['labels']['app'] = "{{ .Values.name }}"
    val['spec']['template']['spec']['containers'][0]['image'] = "{{ .Values.repository.image }}"+":"+"{{ .Values.repository.tag}}"
    val['spec']['template']['spec']['containers'][0]['name'] = "{{ .Values.name }}"
    val['metadata']['namespace'] = "{{ .Release.Namespace }}"
    val['metadata']['name'] = "{{ .Values.name }}"
    
    with open(values_yaml_file, 'w') as file:
        yaml.dump(values, file, default_flow_style=False)

    output_dc_path = os.path.join(templates_directory, f"{app_name}_deployment.yaml") 
    with open(output_dc_path, "w") as f:
        yaml.dump(val, f)  

    cleanup_yaml_files(templates_directory)  
        

# Process all YAML files in the input folder
for file_name in os.listdir(input_folder):
    if file_name.endswith('.yaml') or file_name.endswith('.yml'):
        input_file_path = os.path.join(input_folder, file_name)
        process_file(input_file_path)
        
