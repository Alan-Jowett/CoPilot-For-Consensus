// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to provision a small Linux VM as API gateway to eliminate Azure Load Balancer costs'
metadata author = 'Copilot-for-Consensus Team'

@description('Location for resources')
param location string

@description('Project name')
param projectName string

@description('Environment name')
param environment string

@description('Gateway VM size')
@allowed(['Standard_B1ls', 'Standard_B1s', 'Standard_B2s'])
param vmSize string = 'Standard_B1ls'

@description('Admin username for the VM')
param adminUsername string

@description('SSH public key for admin access')
@secure()
param sshPublicKey string

@description('Gateway subnet ID')
param subnetId string

@description('Internal FQDNs of Container Apps services for nginx routing')
param serviceFqdns object

@description('Enable public IP for the VM')
param enablePublicIp bool = true

param tags object = {}

var uniqueSuffix = uniqueString(resourceGroup().id)
var projectPrefix = take(replace(projectName, '-', ''), 8)
var vmName = '${projectPrefix}-gw-vm-${environment}'
var nicName = '${vmName}-nic'
var publicIpName = '${vmName}-pip'
var nsgName = '${vmName}-nsg'

// Network Security Group - Allow HTTP/HTTPS inbound, all outbound
resource nsg 'Microsoft.Network/networkSecurityGroups@2024-01-01' = {
  name: nsgName
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'Allow-HTTP-Inbound'
        properties: {
          priority: 100
          protocol: 'Tcp'
          access: 'Allow'
          direction: 'Inbound'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '80'
        }
      }
      {
        name: 'Allow-HTTPS-Inbound'
        properties: {
          priority: 110
          protocol: 'Tcp'
          access: 'Allow'
          direction: 'Inbound'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '443'
        }
      }
      {
        name: 'Allow-SSH-Inbound'
        properties: {
          priority: 120
          protocol: 'Tcp'
          access: 'Allow'
          direction: 'Inbound'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '22'
        }
      }
      {
        name: 'Allow-All-Outbound'
        properties: {
          priority: 100
          protocol: '*'
          access: 'Allow'
          direction: 'Outbound'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '*'
        }
      }
    ]
  }
}

// Public IP (optional, for external access)
resource publicIp 'Microsoft.Network/publicIPAddresses@2024-01-01' = if (enablePublicIp) {
  name: publicIpName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
    dnsSettings: {
      domainNameLabel: toLower('${projectPrefix}-gw-${environment}-${take(uniqueSuffix, 5)}')
    }
  }
}

// Network Interface
resource nic 'Microsoft.Network/networkInterfaces@2024-01-01' = {
  name: nicName
  location: location
  tags: tags
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          subnet: {
            id: subnetId
          }
          privateIPAllocationMethod: 'Dynamic'
          publicIPAddress: enablePublicIp ? {
            id: publicIp.id
          } : null
        }
      }
    ]
    networkSecurityGroup: {
      id: nsg.id
    }
  }
}

// Cloud-init script for nginx installation and configuration
// Use string interpolation to inject FQDNs directly
var cloudInitScript = '''#cloud-config
package_update: true
package_upgrade: true

packages:
  - nginx
  - curl

write_files:
  - path: /etc/nginx/sites-available/copilot-gateway
    content: |
      # Copilot-for-Consensus Gateway
      # Routes traffic to internal Container Apps services
      
      upstream reporting {
        server REPORTING_FQDN_PLACEHOLDER:443;
      }
      
      upstream ingestion {
        server INGESTION_FQDN_PLACEHOLDER:443;
      }
      
      upstream auth {
        server AUTH_FQDN_PLACEHOLDER:443;
      }
      
      upstream ui {
        server UI_FQDN_PLACEHOLDER:443;
      }
      
      upstream orchestrator {
        server ORCHESTRATOR_FQDN_PLACEHOLDER:443;
      }
      
      upstream summarization {
        server SUMMARIZATION_FQDN_PLACEHOLDER:443;
      }
      
      upstream parsing {
        server PARSING_FQDN_PLACEHOLDER:443;
      }
      
      upstream chunking {
        server CHUNKING_FQDN_PLACEHOLDER:443;
      }
      
      upstream embedding {
        server EMBEDDING_FQDN_PLACEHOLDER:443;
      }
      
      server {
        listen 80 default_server;
        listen [::]:80 default_server;
        server_name _;
        
        # Health check endpoint
        location /health {
          access_log off;
          return 200 "OK\n";
          add_header Content-Type text/plain;
        }
        
        # Reporting service
        location /reporting/ {
          proxy_pass https://reporting/;
          proxy_set_header Host REPORTING_FQDN_PLACEHOLDER;
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
          proxy_ssl_server_name on;
          proxy_ssl_verify off;
        }
        
        # Ingestion service
        location /ingestion/ {
          proxy_pass https://ingestion/;
          proxy_set_header Host INGESTION_FQDN_PLACEHOLDER;
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
          proxy_ssl_server_name on;
          proxy_ssl_verify off;
        }
        
        # Auth service
        location /auth/ {
          proxy_pass https://auth/;
          proxy_set_header Host AUTH_FQDN_PLACEHOLDER;
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
          proxy_ssl_server_name on;
          proxy_ssl_verify off;
        }
        
        # UI service
        location /ui/ {
          proxy_pass https://ui/;
          proxy_set_header Host UI_FQDN_PLACEHOLDER;
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
          proxy_ssl_server_name on;
          proxy_ssl_verify off;
        }
        
        # Orchestrator service
        location /orchestrator/ {
          proxy_pass https://orchestrator/;
          proxy_set_header Host ORCHESTRATOR_FQDN_PLACEHOLDER;
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
          proxy_ssl_server_name on;
          proxy_ssl_verify off;
        }
        
        # Summarization service
        location /summarization/ {
          proxy_pass https://summarization/;
          proxy_set_header Host SUMMARIZATION_FQDN_PLACEHOLDER;
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
          proxy_ssl_server_name on;
          proxy_ssl_verify off;
        }
        
        # Parsing service
        location /parsing/ {
          proxy_pass https://parsing/;
          proxy_set_header Host PARSING_FQDN_PLACEHOLDER;
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
          proxy_ssl_server_name on;
          proxy_ssl_verify off;
        }
        
        # Chunking service
        location /chunking/ {
          proxy_pass https://chunking/;
          proxy_set_header Host CHUNKING_FQDN_PLACEHOLDER;
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
          proxy_ssl_server_name on;
          proxy_ssl_verify off;
        }
        
        # Embedding service
        location /embedding/ {
          proxy_pass https://embedding/;
          proxy_set_header Host EMBEDDING_FQDN_PLACEHOLDER;
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
          proxy_ssl_server_name on;
          proxy_ssl_verify off;
        }
        
        # Default redirect to UI
        location / {
          return 302 /ui/;
        }
      }

  - path: /usr/local/bin/configure-gateway.sh
    permissions: '0755'
    content: |
      #!/bin/bash
      set -e
      
      # Nginx config is already populated with FQDNs at deployment time
      # Enable the site
      ln -sf /etc/nginx/sites-available/copilot-gateway /etc/nginx/sites-enabled/
      rm -f /etc/nginx/sites-enabled/default
      
      # Test and reload nginx
      nginx -t
      systemctl reload nginx

runcmd:
  - systemctl enable nginx
  - systemctl start nginx
  - /usr/local/bin/configure-gateway.sh

final_message: "Gateway VM is ready. Nginx configured to route to Container Apps internal endpoints."
'''

// Substitute FQDNs in cloud-init script
var cloudInitWithFqdns = replace(cloudInitScript, 'REPORTING_FQDN_PLACEHOLDER', serviceFqdns.reporting)
var cloudInitWithFqdns2 = replace(cloudInitWithFqdns, 'INGESTION_FQDN_PLACEHOLDER', serviceFqdns.ingestion)
var cloudInitWithFqdns3 = replace(cloudInitWithFqdns2, 'AUTH_FQDN_PLACEHOLDER', serviceFqdns.auth)
var cloudInitWithFqdns4 = replace(cloudInitWithFqdns3, 'UI_FQDN_PLACEHOLDER', serviceFqdns.ui)
var cloudInitWithFqdns5 = replace(cloudInitWithFqdns4, 'ORCHESTRATOR_FQDN_PLACEHOLDER', serviceFqdns.orchestrator)
var cloudInitWithFqdns6 = replace(cloudInitWithFqdns5, 'SUMMARIZATION_FQDN_PLACEHOLDER', serviceFqdns.summarization)
var cloudInitWithFqdns7 = replace(cloudInitWithFqdns6, 'PARSING_FQDN_PLACEHOLDER', serviceFqdns.parsing)
var cloudInitWithFqdns8 = replace(cloudInitWithFqdns7, 'CHUNKING_FQDN_PLACEHOLDER', serviceFqdns.chunking)
var cloudInitFinal = base64(replace(cloudInitWithFqdns8, 'EMBEDDING_FQDN_PLACEHOLDER', serviceFqdns.embedding))

// Virtual Machine
resource vm 'Microsoft.Compute/virtualMachines@2024-03-01' = {
  name: vmName
  location: location
  tags: tags
  properties: {
    hardwareProfile: {
      vmSize: vmSize
    }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: '0001-com-ubuntu-server-jammy'
        sku: '22_04-lts-gen2'
        version: 'latest'
      }
      osDisk: {
        createOption: 'FromImage'
        managedDisk: {
          storageAccountType: 'Standard_LRS'
        }
        diskSizeGB: 30
      }
    }
    osProfile: {
      computerName: vmName
      adminUsername: adminUsername
      customData: cloudInitFinal
      linuxConfiguration: {
        disablePasswordAuthentication: true
        ssh: {
          publicKeys: [
            {
              path: '/home/${adminUsername}/.ssh/authorized_keys'
              keyData: sshPublicKey
            }
          ]
        }
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: nic.id
        }
      ]
    }
  }
}

// Outputs
@description('Gateway VM name')
output vmName string = vm.name

@description('Gateway VM resource ID')
output vmId string = vm.id

@description('Gateway VM private IP address')
output privateIpAddress string = nic.properties.ipConfigurations[0].properties.privateIPAddress

@description('Gateway VM public IP address')
output publicIpAddress string = enablePublicIp ? publicIp!.properties.ipAddress : ''

@description('Gateway VM public FQDN')
output publicFqdn string = enablePublicIp ? publicIp!.properties.dnsSettings.fqdn : ''

@description('Gateway health endpoint URL')
output healthEndpoint string = enablePublicIp ? 'http://${publicIp!.properties.dnsSettings.fqdn}/health' : 'http://${nic.properties.ipConfigurations[0].properties.privateIPAddress}/health'
