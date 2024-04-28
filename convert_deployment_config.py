import yaml
import os
from pathlib import Path
import re

# Define input, output, and intermediate directories
input_folder = 'sourceDirectory'
output_folder = 'outputDirectory'
conversion_items_folder = 'workingDirectory'
registry_url = 'image-registry.openshift-image-registry.svc:5000'
subdomain = 'apps.033gl.gl.cl'

# Ensure the output and intermediate folders exist; create them if not
os.makedirs(output_folder, exist_ok=True)
os.makedirs(conversion_items_folder, exist_ok=True)

def convert_deploymentconfig_to_deployment(data):
    data['kind'] = 'Deployment'
    data['apiVersion'] = 'apps/v1'

    # Cleanup spec.selector
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

    # Clean up spec.strategy
    try:
        data['spec']['strategy']['type'] = 'RollingUpdate'
        data['spec']['strategy'] = {key: value for key, value in data['spec']['strategy'].items() if key == 'type'}
    except KeyError:
        pass
    
    # Extract image name
    try:
        for k in data['spec']['triggers']:
            if 'imageChangeParams' in k:

                imageName = (k['imageChangeParams']['from']['name']).split(':')[0]                
                imagePath = k['imageChangeParams']['from']['namespace']
                newImage = registry_url + '/' + imagePath + '/' + imageName
                imageFullPath = imageName + '-' + imagePath
                data['spec']['template']['spec']['containers'][0]['image'] = newImage
    except (KeyError, IndexError):
        print(f"Error handling imageChangeParams in manifest {data['metadata'].get('name')}, skipping.")

    # Remove uneeded fields
    keys_to_remove = ['triggers', 'test', 'resources', 'status', 'revisionHistoryLimit']
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

    return [data, imageFullPath]


def modify_yaml(file_path, output_file_path):
    """
    Reads a YAML file and modifies its contents:
    1. Removes single quotes from Helm template expressions like '{{}}'.
    """

    quotes_pattern = re.compile(r"'{{.*?}}'") 
    env_pattern = re.compile(r'\${ENVIRONMENT}') 

    with open(file_path, 'r') as file:
        lines = file.readlines()
    modified_lines = []

    for line in lines:
        modified_line = quotes_pattern.sub(lambda m: m.group(0).strip("'"), line)
        modified_line = env_pattern.sub('{{ .Values.env }}', modified_line)
        modified_lines.append(modified_line)

    with open(output_file_path, 'w') as output_file:
        output_file.writelines(modified_lines)

def cleanup_yaml_files(directory_path):
    """
    Processes all YAML files in the specified directory.
    """

    files = os.listdir(directory_path)

    for file_name in files:
        if file_name.endswith('.yaml') or file_name.endswith('.yml'):
            file_path = os.path.join(directory_path, file_name)
            output_file_path = file_path 
            modify_yaml(file_path, output_file_path)

def replace_string(data, old_string, new_string):
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str):
                data[key] = value.replace(old_string, new_string)
            elif isinstance(value, dict) or isinstance(value, list):
                replace_string(value, old_string, new_string)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, str):
                data[i] = item.replace(old_string, new_string)
            elif isinstance(item, dict) or isinstance(item, list):
                replace_string(item, old_string, new_string)


def process_file(input_file_path, app_name):
    """
    Process the given file by converting DeploymentConfig to Deployment.
    """
    try:
        # Load the YAML file
        with open(input_file_path, 'r') as file:
            hold_deploymentconfigs = list(yaml.load_all(file, Loader=yaml.SafeLoader))
            app_name = app_name.split('.')[0]+'-app'

            param_export = {}

            try:
                params = hold_deploymentconfigs[0]['parameters']
                for item in params:
                    param_export[item['name'].lower()] = item.get('value', '')
            except:
                params = {}
                pass    


            try:
                if 'app_name' in param_export:
                    new_app_name = param_export['app_name']
                else:
                    new_app_name = ''
            except:
                pass
            
            if 'objects' in hold_deploymentconfigs[0]:
                list_objects = hold_deploymentconfigs[0]['objects']
                try:
                    replace_string(list_objects, '${APP_NAME}', new_app_name)
                    replace_string(list_objects, '${ROUTING_SUFFIX}', '{{.Values.route.domain}}')
                    replace_string(list_objects, '${ENVIRONMENT}', '{{.Values.environment}}')
                    replace_string(list_objects, '${APP_PATH_EN}', '{{.Values.app_path_en}}')
                    replace_string(list_objects, '${APP_PATH_FR}', '{{.Values.app_path_fr}}')
                    replace_string(list_objects, '${LANGUAGE_MATRIX}', '{{.Values.lang_matrix}}')
                    replace_string(list_objects, '${PVC_SIZE}', '{{.Values.pvc_size}}')
                except:
                    pass
            else:
                list_objects = hold_deploymentconfigs
                try:
                    replace_string(list_objects, '${APP_NAME}', new_app_name)
                    replace_string(list_objects, '${ROUTING_SUFFIX}', '{{.Values.route.domain}}')
                    replace_string(list_objects, '${ENVIRONMENT}', '{{.Values.environment}}')
                    replace_string(list_objects, '${APP_PATH_EN}', '{{.Values.app_path_en}}')
                    replace_string(list_objects, '${APP_PATH_FR}', '{{.Values.app_path_fr}}')
                    replace_string(list_objects, '${LANGUAGE_MATRIX}', '{{.Values.lang_matrix}}')
                    replace_string(list_objects, '${LANGUAGE_MATRIX}', '{{.Values.pvc_size}}')
                except:
                    pass


            ## Generate Helm Chart boiler plate
                
            generate_helm_chart_boilerplate(app_name)  

            
            values = {}       

            ## If a template file, Extract different components
            for l in list_objects:  
                if l['kind'] == 'DeploymentConfig':
                    thisAppName = l['metadata']['name']
                    file_path_dc =  conversion_items_folder + '/' + thisAppName + '_deploymentconfig.yaml'
                    with open(file_path_dc, 'w') as file:            
                       yaml.dump(l, file)               
                    print(app_name + " deploymentconfig done... ")
                    print()
                    deploy = generate_helm_chart_deployment_data(l, app_name, thisAppName, values, param_export, new_app_name)
                    values.update(deploy)

                if l['kind'] == 'Service':
                    thisAppName = l['metadata']['name']
                    file_path_svc =  conversion_items_folder + '/' + thisAppName + '_service.yaml'
                    with open(file_path_svc, 'w') as file:            
                       yaml.dump(l, file)
                    print(app_name + " service done... ")
                    print()
                    update_service_helm_values(l, app_name, thisAppName)

                if l['kind'] == 'Route':
                    thisAppName = l['metadata']['name']
                    file_path_route =  conversion_items_folder + '/' + thisAppName + '_route.yaml'
                    with open(file_path_route, 'w') as file:            
                       yaml.dump(l, file)
                    print( app_name + " route done... ")
                    print()
                    update_route_helm_values(l, app_name, thisAppName)

                if l['kind'] == 'CronJob':
                    thisAppName = l['metadata']['name']
                    file_path_cronjob =  conversion_items_folder + '/' + thisAppName + '_cronjob.yaml'
                    with open(file_path_cronjob, 'w') as file:            
                       yaml.dump(l, file)
                    print(app_name + " cronjob done... ")
                    print()
                    update_cronjob_helm_values(l, app_name, thisAppName)

                if l['kind'] == 'PersistentVolumeClaim':
                    thisAppName = l['metadata']['name']
                    file_path_pvc =  conversion_items_folder + '/' + thisAppName + '_pvc.yaml'
                    with open(file_path_pvc, 'w') as file:            
                       yaml.dump(l, file)
                    print(app_name + " pvc done... ")
                    print()
                    update_pvc_helm_values(l, app_name, thisAppName)

                if l['kind'] == 'StatefulSet':
                    thisAppName= l['metadata']['name']
                    file_path_statefulset =  conversion_items_folder + '/' + thisAppName + '_statefulset.yaml'
                    with open(file_path_statefulset, 'w') as file:            
                       yaml.dump(l, file)
                    print(app_name + " statefulset done... ")
                    print()
                    ssReturn = update_statefulset_helm_values (l, app_name, thisAppName)
                    values['repository'].update(ssReturn)

            helm_chart_directory = output_folder + "/" + app_name
            values_yaml_file = os.path.join(helm_chart_directory, 'values.yaml')
            with open(values_yaml_file, 'w') as file:
                yaml.dump(values, file, default_flow_style=False)

    except Exception as e:
        print(f"Error processing file {input_file_path}: {e}")

def generate_helm_chart_resources (data, app_name, resourceType, thisAppName):
    helm_output_resource_path = output_folder + '/' + app_name + '/' + 'templates' + '/' + f'{thisAppName}_{resourceType}.yaml'
    helm_templates_directory = output_folder + '/' + app_name + '/' + 'templates'

    # Dump YAML data to the file
    with open(helm_output_resource_path, 'w') as file:
        yaml.dump(data, file)
    cleanup_yaml_files(helm_templates_directory) 


def update_route_helm_values(data, app_name, thisAppName): 

    data['metadata']['namespace'] = '{{ .Release.namespace }}'

    if 'labels' in data['metadata']:
        data['metadata']['labels'].update({'app': '{{.Values.name}}'})

    generate_helm_chart_resources(data, app_name, 'route', thisAppName )

def update_service_helm_values (data, app_name, thisAppName): 
    data['metadata']['namespace'] = '{{ .Release.namespace }}'

    if 'selector' in data['spec']:
        data['spec']['selector'].pop('deploymentconfig', None)
        data['spec']['selector']['deployment'] = '{{.Values.name}}'
        data['spec']['selector'].update({'app': '{{.Values.name}}'})

    if 'labels' in data['metadata']:
        data['metadata']['labels'].update({'app': '{{.Values.name}}'})

    generate_helm_chart_resources(data, app_name, 'service', thisAppName)

def update_cronjob_helm_values (data, app_name, thisAppName): 
    data['metadata']['namespace'] = '{{ .Release.namespace }}'

    if 'labels' in data['metadata']:
        data['metadata']['labels'].update({'app': '{{.Values.name}}'})
    else:
        data['metadata'].update({'labels': {'app': '{{.Values.name}}'}})

    generate_helm_chart_resources(data, app_name, 'cronjob', thisAppName)

def update_pvc_helm_values (data, app_name, thisAppName): 
    data['metadata']['namespace'] = '{{ .Release.namespace }}'
    data['spec']['storageClassName'] = '{{ .Values.storageclass }}'

    if 'labels' in data['metadata']:
        data['metadata']['labels'].update({'app': '{{.Values.name}}'})

    generate_helm_chart_resources(data, app_name, 'pvc', thisAppName)
    

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
        

def generate_helm_chart_deployment_data(data, app_name, thisAppName, v, param_export, new_app_name):
    val = convert_deploymentconfig_to_deployment(data)
    helm_chart_directory = output_folder + "/" + app_name
    templates_directory = os.path.join(helm_chart_directory, 'templates')

    matchLine = val[0]['spec']['template']['spec']['containers'][0]['image'].split("/")

    deploymentValues ={}

    if val[0]['metadata']['name']:
        valName = {'name': data['metadata']['name']}
    if val[0]['spec']['replicas']:
        replicas = {'replicas': data['spec']['replicas']}

    # Add app label for the app. Leave other labels
    labelAdd = {'labels': {'app': '{{.Values.name}}'}}
    if 'metadata' in val[0] and 'labels' not in val[0]['metadata']:
       val[0]['metadata'].update(labelAdd)


    values = {
           'route': {
               'name': val[1],
               'domain': subdomain
           },
           'resources': {},
           'repository': {
               'image': matchLine[0],
               'path': matchLine[1],
               'name': matchLine[2],
               'tag': 'dev'
           }
       }

       
    container = val[0]['spec']['template']['spec']['containers'][0]
    
    if 'resources' in container:
        container_resources = container['resources']
        
        if 'limits' in container_resources:
            limits = {
                    'limits': {
                        'cpu': val[0]['spec']['template']['spec']['containers'][0]['resources']['limits']['cpu'],
                        'memory': val[0]['spec']['template']['spec']['containers'][0]['resources']['limits']['memory']
                    }
                }
            values['resources'].update(limits) 
            val[0]['spec']['template']['spec']['containers'][0]['resources']['limits']['cpu'] = "{{ .Values.resources.limits.cpu }}"
            val[0]['spec']['template']['spec']['containers'][0]['resources']['limits']['memory'] = "{{ .Values.resources.limits.memory }}"
    
        if 'requests' in container_resources:
            requests = {
                    'requests': {
                        'cpu': val[0]['spec']['template']['spec']['containers'][0]['resources']['requests']['cpu'],
                        'memory': val[0]['spec']['template']['spec']['containers'][0]['resources']['requests']['memory']
                    }
                }
            values['resources'].update(requests) 
            val[0]['spec']['template']['spec']['containers'][0]['resources']['requests']['cpu'] = "{{ .Values.resources.requests.cpu }}"
            val[0]['spec']['template']['spec']['containers'][0]['resources']['requests']['memory'] = "{{ .Values.resources.requests.memory }}"

    val[0]['spec']['replicas'] = "{{ .Values.replicas }}"
    val[0]['spec']['selector']['matchLabels']['app'] = "{{ .Values.name }}"
    val[0]['spec']['template']['metadata']['labels']['app'] = "{{ .Values.name }}"
    val[0]['spec']['template']['spec']['containers'][0]['image'] = "{{.Values.repository.image}}"+"/"+"{{.Values.repository.path}}"+"/"+"{{.Values.repository.name}}"+":"+"{{.Values.repository.tag}}"
    val[0]['spec']['template']['spec']['containers'][0]['name'] = "{{ .Values.name }}"
    val[0]['metadata']['namespace'] = "{{ .Release.Namespace }}"
    val[0]['metadata']['labels']['app'] = "{{ .Values.name }}"
    
    deploymentValues.update(**valName, **replicas, **values)    

    for key, value in param_export.items():
        if not 'routing_suffix' in key:
            deploymentValues.update({key: value})
        else:
            deploymentValues['route'].update({'routing_suffix': param_export['routing_suffix']})

    output_dc_path = os.path.join(templates_directory, f"{thisAppName}_deployment.yaml") 
    with open(output_dc_path, "w") as f:
        yaml.dump(val[0], f)  

    cleanup_yaml_files(templates_directory) 

    return deploymentValues

def update_statefulset_helm_values (data, app_name, thisAppName):
    data['spec']['replicas'] = "{{ .Values.replicas }}"
    data['spec']['selector']['matchLabels']['app'] = "{{ .Values.name }}"
    data['metadata']['namespace'] = '{{ .Release.namespace }}'
    data['spec']['storageClassName'] = '{{ .Values.storageclass }}'

    ssValues = {}

    matchLine = data['spec']['template']['spec']['containers'][0]['image'].split("/")

    matchImageName = matchLine[2].split(':')[0]

    values = {
           'statefulset': {               
               'image': matchLine[0],
               'path': matchLine[1],
               'name': matchImageName,
               'tag': 'dev'
           }
       }

    if 'labels' in data['metadata']:
        data['metadata']['labels'].update({'app': '{{.Values.name}}'})
    
    data['spec']['template']['spec']['containers'][0]['image'] = "{{.Values.repository.statefulset.image}}"+"/"+"{{.Values.repository.statefulset.path}}"+"/"+"{{.Values.repository.statefulset.name}}"+":"+"{{.Values.repository.statefulset.tag}}"

    generate_helm_chart_resources(data, app_name, 'statefulset', thisAppName)

    return values
        

# Process all YAML files in the input folder
for app_name in os.listdir(input_folder):
    if app_name.endswith('.yaml') or app_name.endswith('.yml'):
        input_file_path = os.path.join(input_folder, app_name)
        process_file(input_file_path, app_name)
        
