#!/usr/bin/env python3
"""
Script para integração com JIRA para extrair issues no formato XML usando JQL
"""
from flask import Flask, request, jsonify
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
import argparse
import os
import sys
from datetime import datetime

app = Flask(__name__)

# Configurações do JIRA (deveriam vir de variáveis de ambiente)
JIRA_CONFIG = {
    'url': os.getenv('JIRA_URL', 'https://your-domain.atlassian.net'),
    'email': os.getenv('JIRA_EMAIL', 'your-email@example.com'),
    'api_token': os.getenv('JIRA_API_TOKEN', 'your-api-token')
}
class JiraXMLExporter:
    def __init__(self, url, email, api_token):
        """
        Inicializa o exportador JIRA
        
        Args:
            url (str): URL base do JIRA (ex: https://seu-dominio.atlassian.net)
            email (str): Email da conta do JIRA
            api_token (str): Token de API do JIRA
        """
        self.base_url = url.rstrip('/')
        self.auth = (email, api_token)
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
    
    def test_connection(self):
        """Testa a conexão com o JIRA"""
        try:
            response = self.session.get(f"{self.base_url}/rest/api/2/myself")
            if response.status_code == 200:
                print(f"Conexão bem-sucedida! Usuário: {response.json()['displayName']}")
                return True
            else:
                print(f"Falha na conexão: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"Erro ao conectar com JIRA: {str(e)}")
            return False
    
    def jql_to_xml(self, jql_query, max_results=100, output_file=None):
        """
        Executa uma consulta JQL e retorna os resultados em formato XML
        
        Args:
            jql_query (str): Consulta JQL
            max_results (int): Número máximo de resultados
            output_file (str): Caminho do arquivo para salvar o XML
            
        Returns:
            str: XML com os resultados ou None em caso de erro
        """
        print(f"Executando consulta JQL: {jql_query}")
        
        # Parâmetros da consulta
        params = {
            'jql': jql_query,
            'maxResults': max_results,
            'fields': '*all',  # Todos os campos
            'expand': 'renderedFields,names,schema,operations,editmeta,changelog,versionedRepresentations'
        }
        
        try:
            # Executar a consulta JQL
            response = self.session.get(
                f"{self.base_url}/rest/api/2/search",
                params=params
            )
            
            if response.status_code != 200:
                print(f"Erro na consulta JQL: {response.status_code} - {response.text}")
                return None
            
            data = response.json()
            issues = data.get('issues', [])
            total = data.get('total', 0)
            
            print(f"Encontradas {total} issues. Convertendo {len(issues)} para XML...")
            
            # Criar o XML base
            rss = ET.Element('rss')
            rss.set('version', '2.0')
            channel = ET.SubElement(rss, 'channel')
            
            ET.SubElement(channel, 'title').text = 'JIRA Export'
            ET.SubElement(channel, 'description').text = f'JIRA Issues Export - Query: {jql_query}'
            ET.SubElement(channel, 'link').text = self.base_url
            ET.SubElement(channel, 'lastBuildDate').text = datetime.now().isoformat()
            
            # Adicionar cada issue como um item
            for issue in issues:
                item = self._issue_to_xml(issue, channel)
            
            # Formatar o XML
            rough_string = ET.tostring(rss, 'utf-8')
            parsed = minidom.parseString(rough_string)
            xml_str = parsed.toprettyxml(indent="  ")
            
            # Salvar em arquivo se especificado
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(xml_str)
                print(f"XML salvo em: {output_file}")
            
            return xml_str
            
        except Exception as e:
            print(f"Erro ao processar consulta JQL: {str(e)}")
            return None
    
    def _issue_to_xml(self, issue, parent_element):
        """Converte uma issue do JIRA para XML"""
        item = ET.SubElement(parent_element, 'item')
        
        # Campos básicos
        ET.SubElement(item, 'title').text = f"[{issue['key']}] {issue['fields'].get('summary', '')}"
        ET.SubElement(item, 'link').text = f"{self.base_url}/browse/{issue['key']}"
        
        # Project
        project = issue['fields'].get('project', {})
        project_elem = ET.SubElement(item, 'project')
        project_elem.set('id', project.get('id', ''))
        project_elem.set('key', project.get('key', ''))
        project_elem.text = project.get('name', '')
        
        # Description
        description = issue['fields'].get('description', '')
        if description:
            # Para preservar formatação HTML se existir
            desc_elem = ET.SubElement(item, 'description')
            desc_elem.text = f"<![CDATA[{description}]]>"
        else:
            ET.SubElement(item, 'description').text = ''
        
        ET.SubElement(item, 'environment').text = issue['fields'].get('environment', '')
        
        # Key
        key_elem = ET.SubElement(item, 'key')
        key_elem.set('id', issue.get('id', ''))
        key_elem.text = issue['key']
        
        # Summary
        ET.SubElement(item, 'summary').text = issue['fields'].get('summary', '')
        
        # Issue Type
        issue_type = issue['fields'].get('issuetype', {})
        type_elem = ET.SubElement(item, 'type')
        type_elem.set('id', issue_type.get('id', ''))
        type_elem.set('iconUrl', issue_type.get('iconUrl', ''))
        type_elem.text = issue_type.get('name', '')
        
        # Priority
        priority = issue['fields'].get('priority', {})
        if priority:
            prio_elem = ET.SubElement(item, 'priority')
            prio_elem.set('id', priority.get('id', ''))
            prio_elem.set('iconUrl', priority.get('iconUrl', ''))
            prio_elem.text = priority.get('name', '')
        
        # Status
        status = issue['fields'].get('status', {})
        if status:
            status_elem = ET.SubElement(item, 'status')
            status_elem.set('id', status.get('id', ''))
            status_elem.set('iconUrl', status.get('iconUrl', ''))
            status_elem.set('description', status.get('description', ''))
            status_elem.text = status.get('name', '')
            
            # Status Category
            status_category = status.get('statusCategory', {})
            if status_category:
                cat_elem = ET.SubElement(item, 'statusCategory')
                cat_elem.set('id', status_category.get('id', ''))
                cat_elem.set('key', status_category.get('key', ''))
                cat_elem.set('colorName', status_category.get('colorName', ''))
        
        # Resolution
        resolution = issue['fields'].get('resolution', {})
        if resolution:
            res_elem = ET.SubElement(item, 'resolution')
            res_elem.set('id', resolution.get('id', ''))
            res_elem.text = resolution.get('name', '')
        
        # Assignee
        assignee = issue['fields'].get('assignee', {})
        if assignee:
            assignee_elem = ET.SubElement(item, 'assignee')
            assignee_elem.set('accountId', assignee.get('accountId', ''))
            assignee_elem.text = assignee.get('displayName', '')
        
        # Reporter
        reporter = issue['fields'].get('reporter', {})
        if reporter:
            reporter_elem = ET.SubElement(item, 'reporter')
            reporter_elem.set('accountId', reporter.get('accountId', ''))
            reporter_elem.text = reporter.get('displayName', '')
        
        # Labels
        labels = issue['fields'].get('labels', [])
        if labels:
            labels_elem = ET.SubElement(item, 'labels')
            for label in labels:
                ET.SubElement(labels_elem, 'label').text = label
        
        # Dates
        for field in ['created', 'updated', 'resolved', 'duedate']:
            value = issue['fields'].get(field, '')
            if value:
                ET.SubElement(item, field).text = value
        
        # Votes and Watches
        votes = issue['fields'].get('votes', {})
        if votes:
            ET.SubElement(item, 'votes').text = str(votes.get('votes', 0))
        
        watches = issue['fields'].get('watches', {})
        if watches:
            ET.SubElement(item, 'watches').text = str(watches.get('watchCount', 0))
        
        # Comments (precisa de expansão adicional)
        if 'comment' in issue['fields']:
            comments = issue['fields']['comment'].get('comments', [])
            if comments:
                comments_elem = ET.SubElement(item, 'comments')
                for comment in comments:
                    comment_elem = ET.SubElement(comments_elem, 'comment')
                    comment_elem.set('id', comment.get('id', ''))
                    comment_elem.set('author', comment.get('author', {}).get('displayName', ''))
                    comment_elem.set('created', comment.get('created', ''))
                    comment_elem.text = comment.get('body', '')
        
        # TODO: Adicionar mais campos conforme necessário
        
        return item

def main():
    parser = argparse.ArgumentParser(description='Exportar issues do JIRA para XML usando JQL')
    parser.add_argument('--url', required=True, help='URL base do JIRA (ex: https://seu-dominio.atlassian.net)')
    parser.add_argument('--email', required=True, help='Email da conta do JIRA')
    parser.add_argument('--api-token', required=True, help='Token de API do JIRA')
    parser.add_argument('--jql', required=True, help='Consulta JQL para buscar issues')
    parser.add_argument('--output', help='Arquivo de saída XML (opcional)')
    parser.add_argument('--max-results', type=int, default=100, help='Número máximo de resultados (padrão: 100)')
    
    args = parser.parse_args()
    
    # Verificar se o token de API foi fornecido
    if not args.api_token:
        print("Erro: Token de API é necessário")
        sys.exit(1)
    
    # Criar exportador
    exporter = JiraXMLExporter(args.url, args.email, args.api_token)
    
    # Testar conexão
    if not exporter.test_connection():
        print("Não foi possível conectar ao JIRA. Verifique suas credenciais e URL.")
        sys.exit(1)
    
    # Executar consulta e gerar XML
    xml_output = exporter.jql_to_xml(
        jql_query=args.jql,
        max_results=args.max_results,
        output_file=args.output
    )
    
    if xml_output:
        if not args.output:
            print(xml_output)
        print("Exportação concluída com sucesso!")
    else:
        print("Falha na exportação.")
        sys.exit(1)

if __name__ == "__main__":
    main()