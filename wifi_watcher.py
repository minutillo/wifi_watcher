#!/usr/bin/env python3

import subprocess
import re
import csv
import sys
import time
from datetime import datetime
from pathlib import Path
import os
import smtplib
import ssl
from email.message import EmailMessage
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
SCAN_INTERVAL_SECONDS = 15
RAW_LOG_FILENAME = "wifi_watcher.log"
CSV_FILENAME = "wifi_watcher.csv"

# --- Main Functions ---
def send_email(subject, body):
	"""
	Constructs and sends an email using the configured credentials and content.
	"""
	# Fetching credentials from environment variables for security
	# Do not hardcode your credentials directly in the script.
	sender_email = os.getenv("SENDER_EMAIL")
	password = os.getenv("SENDER_PASSWORD")
	recipient_email = os.getenv("RECIPIENT_EMAIL")
	
	if not all([sender_email, password, recipient_email]):
		print("One or more environment variables (SENDER_EMAIL, SENDER_PASSWORD, RECIPIENT_EMAIL) are missing.")
		print("Please ensure your .env file is correctly set up.")
		return

	# Create the email message object
	em = EmailMessage()
	em['From'] = sender_email
	em['To'] = recipient_email
	em['Subject'] = subject
	em.set_content(body)

	# Add SSL context for security
	context = ssl.create_default_context()

	try:
		# Connect to Gmail's SMTP server using SSL
		# The 'with' statement ensures the connection is automatically closed
		with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as smtp:
			print("Connecting to Gmail's server...")
			# Log in to your account
			smtp.login(sender_email, password)
			print("Login successful.")
			
			# Send the email
			smtp.send_message(em)
			print(f"Email successfully sent to {recipient_email}!")

	except smtplib.SMTPAuthenticationError:
		print("Authentication failed. Please check the following:")
		print("1. Ensure you are using a 16-digit 'App Password' from Google, not your regular password.")
		print("2. Double-check your SENDER_EMAIL in the .env file.")
	except smtplib.SMTPConnectError:
		print("Failed to connect to the server. Check your internet connection or firewall settings.")
	except Exception as e:
		print(f"An error occurred: {e}")

def get_wifi_profile():
	"""
	Executes the system_profiler command to get Wi-Fi data.
	
	Returns:
		A string containing the command output, or None on error.
	"""
	print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔍  Scanning for Wi-Fi networks...")
	try:
		result = subprocess.run(
			['system_profiler', 'SPAirPortDataType'],
			capture_output=True,
			text=True,
			check=True,
			encoding='utf-8'
		)
		return result.stdout
	except FileNotFoundError:
		print("Error: 'system_profiler' command not found. This script is for macOS only.", file=sys.stderr)
		return None
	except subprocess.CalledProcessError as e:
		print(f"Error executing system_profiler: {e.stderr}", file=sys.stderr)
		return None

def log_raw_output(output):
	"""Appends the raw command output to a log file."""
	try:
		with open(RAW_LOG_FILENAME, 'a', encoding='utf-8') as f:
			f.write(f"\n--- SCAN AT {datetime.now().isoformat()} ---\n")
			f.write(output)
	except IOError as e:
		print(f"Error writing to log file {RAW_LOG_FILENAME}: {e}", file=sys.stderr)

def parse_wifi_data(output):
	"""
	Parses the raw text output, adding a timestamp to each record.
	
	Returns:
		A list of dictionaries, where each dictionary represents a Wi-Fi network.
	"""
	networks = []
	current_section = None
	current_network = None
	timestamp = datetime.now().isoformat()

	# Regex patterns for parsing
	key_value_pattern = re.compile(r'^\s{8}([^:]+):\s(.*)$')
	other_network_pattern = re.compile(r'^\s{6}([^:]+):$')

	for line in output.splitlines():
		if "Current Network Information:" in line:
			current_section = 'current'
			current_network = {"Timestamp": timestamp, "Status": "Connected"}
			continue
		elif "Other Local Wi-Fi Networks:" in line:
			if current_network and current_network.get("SSID"):
				networks.append(current_network)
			current_section = 'other'
			current_network = None
			continue
		
		if current_section == 'current' and current_network is not None:
			match = key_value_pattern.match(line)
			if match:
				key, value = match.groups()
				current_network[key.strip()] = value.strip()
		
		elif current_section == 'other':
			network_match = other_network_pattern.match(line)
			property_match = key_value_pattern.match(line)

			if network_match:
				if current_network:
					networks.append(current_network)
				ssid = network_match.group(1).strip()
				current_network = {"Timestamp": timestamp, "Status": "Available", "SSID": ssid}
			elif property_match and current_network is not None:
				key, value = property_match.groups()
				current_network[key.strip()] = value.strip()

	if current_network:
		networks.append(current_network)
		
	return networks

def append_to_csv(networks):
	"""Appends network data to a CSV file, creating it with headers if it doesn't exist."""
	if not networks:
		return

	csv_path = Path(CSV_FILENAME)
	file_exists = csv_path.is_file()

	# Define a consistent order for columns
	fieldnames = [
		'Timestamp', 'Status', 'SSID', 'BSSID', 'RSSI', 'Noise', 'Channel',
		'Channel Width', 'Security', 'Country Code', 'PHY Mode'
	]

	try:
		with open(csv_path, 'a', newline='', encoding='utf-8') as csvfile:
			writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
			if not file_exists:
				writer.writeheader()
			writer.writerows(networks)
	except IOError as e:
		print(f"Error writing to CSV file {CSV_FILENAME}: {e}", file=sys.stderr)

def check_for_new_networks(networks, known_ssids):
	"""
	Compares current SSIDs with previously known SSIDs and prints new discoveries.
	
	Args:
		networks (list): The list of network dictionaries from the current scan.
		known_ssids (set): A set of SSIDs seen in previous scans.
		
	Returns:
		A new set containing all SSIDs seen up to this point.
	"""
	current_ssids = {net.get("SSID") for net in networks if net.get("SSID")}
	
	newly_discovered = current_ssids - known_ssids
	
	if newly_discovered:
		subject = "New WiFi network(s) detected"
		body = ""
		for ssid in newly_discovered:
			body += f"{ssid}\n"
			print(f"{ssid}")
		print(f"{subject}:{ssid}")
		send_email(subject, body)

	return known_ssids.union(current_ssids)

def main():
	"""Main execution loop."""
	known_ssids = set()
	print("Starting continuous Wi-Fi monitoring. Press Ctrl+C to stop.")
	
	try:
		while True:
			wifi_output = get_wifi_profile()
			
			if wifi_output:
				# 1. Log the raw output
				log_raw_output(wifi_output)
				
				# 2. Parse the data
				parsed_data = parse_wifi_data(wifi_output)
				
				# 3. Append parsed data to CSV
				append_to_csv(parsed_data)
				
				# 4. Check for new networks and update our set of known ones
				known_ssids = check_for_new_networks(parsed_data, known_ssids)
			
			print(f"Scan complete. Next scan in {SCAN_INTERVAL_SECONDS} seconds...")
			time.sleep(SCAN_INTERVAL_SECONDS)
			
	except KeyboardInterrupt:
		print("\n👋  Monitoring stopped by user. Exiting.")
		sys.exit(0)

if __name__ == "__main__":
	main()
