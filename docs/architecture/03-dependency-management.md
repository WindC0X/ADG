## Dependency Version Management System

### Overview

Based on the version management flaws identified in the architecture validation report, the ADG platform must establish a strict dependency version management system. The current wide version ranges (e.g., Python "3.x", pandas "1.5.x-2.3.x") introduce compatibility risks and security vulnerabilities, requiring version control to be precise down to the patch level.

### Version Management Principles

1.  **Exact Version Pinning**: All dependencies are locked to specific patch versions.
2.  **Security First**: Promptly update security patches and review vulnerabilities.
3.  **Compatibility Guarantee**: Thoroughly test before upgrading versions.
4.  **License Compliance**: Strictly review third-party dependency licenses.
5.  **Supply Chain Security**: Verify dependency sources and integrity.

### Precise Version Requirements

#### Core Runtime Version

```yaml
# Precise Core Runtime Version (replaces vague "3.x" version)
runtime:
  python: "3.11.7"              # Pinned to a specific patch version
  python_min: "3.11.0"          # Minimum supported version
  python_max: "3.12.99"         # Maximum compatible version

  # System dependencies
  windows_min: "Windows 10 1909" # Minimum Windows version
  memory_required: "8GB"         # Hardware requirements unchanged
  cpu_required: "i5-9400 or higher"
```

#### Existing Technology Stack Version Pinning

```yaml
# Existing Technology Stack - Exact Version Pinning
existing_stack:
  gui_framework:
    tkinter: "Built-in (Python 3.11.7)"  # Follows Python version
  
  excel_automation:
    xlwings: "0.30.13"           # Pinned to a stable version
    openpyxl: "3.1.2"            # Latest stable version
    pywin32: "306"               # Pinned version
  
  data_processing:
    pandas: "2.1.4"              # Replaces "1.5.x-2.3.x" range
    numpy: "1.25.2"              # pandas dependency
  
  image_processing:
    pillow: "10.1.0"             # Latest secure version
  
  system_integration:
    win32api: "pywin32==306"     # System integration
    win32print: "pywin32==306"
    win32gui: "pywin32==306"
```

#### New Technology Stack Version Definition

```yaml
# New Technology Stack - First-time Precise Version Definition
new_stack:
  workflow_engine:
    sqlite3: "Built-in (Python 3.11.7)"  # Use built-in SQLite
  
  ai_models:
    # Precise LLM model versions
    hunyuan_1_8b: "hunyuan-1.8B-INT4-20240815"
    qwen_4b: "Qwen3-4B-Instruct-INT4-20240820" 
    qwen_7b: "Qwen3-7B-Chat-INT4-20240820"
  
    # Model frameworks
    torch: "2.1.1+cpu"         # CPU version to avoid CUDA dependency
    transformers: "4.36.2"     # Stable version
  
  ocr_engines:
    # UMI-OCR (external HTTP service)
    umi_ocr_version: "2.1.2"   # Explicitly supported version
  
    # Embedded OCR fallback
    paddleocr: "2.7.3"         # Stable version
    paddlepaddle: "2.5.2"      # CPU version
    openvino: "2023.2.0"       # Intel optimization
  
    # Advanced OCR (on-demand)
    dots_ocr: "1.2.3"          # Explicit version requirement
  
  pdf_processing:
    pymupdf: "1.23.8"          # Latest stable version
    fitz: "0.0.1"              # PyMuPDF alias
  
  security_auth:
    pyjwt: "2.8.0"             # JWT handling
    cryptography: "41.0.7"     # Cryptography library
    bcrypt: "4.1.2"            # Password hashing
  
  api_framework:
    flask: "3.0.0"             # Web framework (if API is needed)
    flask_cors: "4.0.0"        # CORS support
    werkzeug: "3.0.1"          # WSGI utility
  
  development_tools:
    black: "23.12.0"           # Code formatter
    isort: "5.13.2"            # Import sorter
    flake8: "6.1.0"            # Linter
    mypy: "1.7.1"              # Type checker
    pytest: "7.4.3"            # Testing framework
    coverage: "7.3.3"          # Test coverage
```

### Dependency Locking Mechanism

#### `requirements.lock` Structure

```ini
# requirements.lock - Pinned version lock file
# Generation time: 2025-08-17
# Python version: 3.11.7
# Target platform: Windows x86_64

# Core dependencies - exact versions
pandas==2.1.4
numpy==1.25.2
openpyxl==3.1.2
xlwings==0.30.13
pywin32==306
pillow==10.1.0

# AI/ML dependencies
torch==2.1.1+cpu
transformers==4.36.2
paddleocr==2.7.3
paddlepaddle==2.5.2
openvino==2023.2.0

# PDF processing
pymupdf==1.23.8

# Security and authentication
pyjwt==2.8.0
cryptography==41.0.7
bcrypt==4.1.2

# API framework (optional)
flask==3.0.0
flask-cors==4.0.0
werkzeug==3.0.1

# Transitive dependencies (auto-resolved)
pytz==2023.3.post1
python-dateutil==2.8.2
six==1.16.0
certifi==2023.11.17
charset-normalizer==3.3.2
idna==3.6
urllib3==2.1.0
requests==2.31.0

# Verification hashes (anti-tampering)
--hash=sha256:abc123...  # 由脚本/pip-compile --generate-hashes 生成
```

#### Version Locking Script

```python
# scripts/lock_dependencies.py
"""
Dependency version locking script.
Automatically generates the requirements.lock file.
"""

import subprocess
import hashlib
import sys
from typing import List, Dict

class DependencyLocker:
    """Dependency version locker"""
  
    def __init__(self):
        self.python_version = sys.version_info
        self.platform = sys.platform
      
    def generate_lock_file(self, requirements_file: str = "requirements.txt"):
        """Generate the lock file"""
        # 1. Resolve dependencies in the current environment
        installed_packages = self.get_installed_packages()
      
        # 2. Calculate dependency hashes
        package_hashes = self.calculate_package_hashes(installed_packages)
      
        # 3. Generate the lock file
        self.write_lock_file(installed_packages, package_hashes)
      
        # 4. Verify the lock file
        self.verify_lock_file()
      
    def get_installed_packages(self) -> List[Dict]:
        """Get the list of installed packages"""
        result = subprocess.run(
            [sys.executable, "-m", "pip", "freeze", "--all"],
            capture_output=True,
            text=True
        )
      
        packages = []
        for line in result.stdout.split('\n'):
            if '==' in line:
                name, version = line.strip().split('==')
                packages.append({'name': name, 'version': version})
              
        return packages
      
    def calculate_package_hashes(self, packages: List[Dict]) -> Dict[str, str]:
        """Calculate package hashes"""
        hashes = {}
        for pkg in packages:
            # Download package file first, then hash the file
            try:
                # Step 1: Download package to get distribution file
                download_result = subprocess.run([
                    sys.executable, "-m", "pip", "download", "--no-deps", 
                    f"{pkg['name']}=={pkg['version']}", "--dest", "temp_download"
                ], capture_output=True, text=True)
                
                if download_result.returncode == 0:
                    # Step 2: Find downloaded file
                    download_dir = Path("temp_download")
                    pkg_files = list(download_dir.glob(f"{pkg['name'].replace('-', '_')}*"))
                    
                    if pkg_files:
                        pkg_file = pkg_files[0]
                        # Step 3: Calculate hash of the file
                        hash_result = subprocess.run([
                            sys.executable, "-m", "pip", "hash", str(pkg_file)
                        ], capture_output=True, text=True)
                        
                        if hash_result.returncode == 0:
                            hashes[pkg['name']] = hash_result.stdout.strip()
                            
                        # Cleanup downloaded file
                        pkg_file.unlink()
                        
            except Exception as e:
                logger.warning(f"Failed to calculate hash for {pkg['name']}: {e}")
                # Alternative: Use pip-compile with --generate-hashes
                try:
                    compile_result = subprocess.run([
                        "pip-compile", "--generate-hashes", "--no-emit-index-url",
                        "--output-file", f"temp_{pkg['name']}.txt"
                    ], input=f"{pkg['name']}=={pkg['version']}", 
                       text=True, capture_output=True)
                    
                    if compile_result.returncode == 0:
                        # Extract hash from compiled output
                        with open(f"temp_{pkg['name']}.txt") as f:
                            content = f.read()
                            hash_match = re.search(r'--hash=([^\s]+)', content)
                            if hash_match:
                                hashes[pkg['name']] = hash_match.group(1)
                        
                        Path(f"temp_{pkg['name']}.txt").unlink()
                        
                except Exception:
                    logger.error(f"All hash calculation methods failed for {pkg['name']}")
              
        return hashes
      
    def write_lock_file(self, packages: List[Dict], hashes: Dict[str, str]):
        """Write the lock file"""
        with open('requirements.lock', 'w', encoding='utf-8') as f:
            # Header information
            f.write(f"# requirements.lock - Pinned version lock file\n")
            f.write(f"# Generation time: {datetime.now().isoformat()}\n")
            f.write(f"# Python version: {sys.version}\n")
            f.write(f"# Target platform: {sys.platform}\n\n")
          
            # Package dependencies
            for pkg in sorted(packages, key=lambda x: x['name']):
                f.write(f"{pkg['name']}=={pkg['version']}")
                if pkg['name'] in hashes:
                    f.write(f" --hash={hashes[pkg['name']]}")
                f.write("\n")
```

### Security Vulnerability Management

#### Vulnerability Scanning Mechanism

```python
# utils/security_scanner.py
"""
Dependency security vulnerability scanner.
"""

import subprocess
import json
import logging
from typing import List, Dict
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Vulnerability:
    """Vulnerability information"""
    package: str
    version: str
    vulnerability_id: str
    severity: str
    description: str
    fixed_version: str = None

class SecurityScanner:
    """Security vulnerability scanner"""
  
    def __init__(self):
        self.vulnerability_db = self.load_vulnerability_db()
      
    def scan_dependencies(self, requirements_file: str = "requirements.lock") -> List[Vulnerability]:
        """Scan dependencies for vulnerabilities"""
        vulnerabilities = []
      
        # 1. Scan using safety
        safety_results = self.run_safety_scan(requirements_file)
        vulnerabilities.extend(safety_results)
      
        # 2. Scan using pip-audit
        audit_results = self.run_pip_audit(requirements_file)
        vulnerabilities.extend(audit_results)
      
        # 3. Deduplicate and prioritize
        return self.deduplicate_and_prioritize(vulnerabilities)
      
    def run_safety_scan(self, requirements_file: str) -> List[Vulnerability]:
        """Run a safety scan"""
        try:
            result = subprocess.run(
                ["safety", "check", "-r", requirements_file, "--json"],
                capture_output=True,
                text=True
            )
          
            if result.returncode == 0:
                return []  # No vulnerabilities
              
            safety_data = json.loads(result.stdout)
            return self.parse_safety_results(safety_data)
          
        except Exception as e:
            logging.error(f"Safety scan failed: {e}")
            return []
          
    def run_pip_audit(self, requirements_file: str) -> List[Vulnerability]:
        """Run a pip-audit scan"""
        try:
            result = subprocess.run(
                ["pip-audit", "-r", requirements_file, "--format", "json"],
                capture_output=True,
                text=True
            )
          
            audit_data = json.loads(result.stdout)
            return self.parse_audit_results(audit_data)
          
        except Exception as e:
            logging.error(f"pip-audit scan failed: {e}")
            return []
          
    def generate_security_report(self, vulnerabilities: List[Vulnerability]) -> Dict:
        """Generate a security report"""
        return {
            'scan_date': datetime.now().isoformat(),
            'total_vulnerabilities': len(vulnerabilities),
            'critical_count': sum(1 for v in vulnerabilities if v.severity == 'critical'),
            'high_count': sum(1 for v in vulnerabilities if v.severity == 'high'),
            'medium_count': sum(1 for v in vulnerabilities if v.severity == 'medium'),
            'low_count': sum(1 for v in vulnerabilities if v.severity == 'low'),
            'vulnerabilities': [asdict(v) for v in vulnerabilities],
            'recommendations': self.generate_recommendations(vulnerabilities)
        }
```

#### Automated Security Updates

```python
# scripts/security_updater.py
"""
Automated security update script.
"""

class SecurityUpdater:
    """Security updater"""
  
    def __init__(self):
        self.scanner = SecurityScanner()
      
    def auto_update_security_patches(self, dry_run: bool = True) -> Dict:
        """Automatically update security patches"""
        # 1. Scan for current vulnerabilities
        vulnerabilities = self.scanner.scan_dependencies()
      
        # 2. Filter for auto-fixable vulnerabilities
        auto_fixable = self.filter_auto_fixable(vulnerabilities)
      
        # 3. Generate an update plan
        update_plan = self.generate_update_plan(auto_fixable)
      
        if not dry_run:
            # 4. Execute updates
            self.execute_updates(update_plan)
          
            # 5. Re-scan to verify
            self.verify_updates()
          
        return {
            'vulnerabilities_found': len(vulnerabilities),
            'auto_fixable': len(auto_fixable),
            'update_plan': update_plan,
            'dry_run': dry_run
        }
      
    def filter_auto_fixable(self, vulnerabilities: List[Vulnerability]) -> List[Vulnerability]:
        """Filter for auto-fixable vulnerabilities"""
        auto_fixable = []
      
        for vuln in vulnerabilities:
            # Only auto-fix vulnerabilities with a clear fixed version
            if (vuln.fixed_version and 
                vuln.severity in ['critical', 'high'] and
                self.is_safe_to_update(vuln.package, vuln.fixed_version)):
                auto_fixable.append(vuln)
              
        return auto_fixable
```

### AI Model License Compliance

#### Model License Review

```yaml
# ai_model_licenses.yaml
ai_model_licenses:
  hunyuan_models:
    hunyuan_1_8b:
      version: "hunyuan-1.8B-INT4-20240815"
      license: "Apache 2.0"
      commercial_use: true
      attribution_required: true
      source: "Tencent Cloud"
      compliance_status: "Under Review"
      legal_review_date: "2025-08-17"
    
  qwen_models:
    qwen_4b:
      version: "Qwen3-4B-Instruct-INT4-20240820"
      license: "Tongyi Qianwen License"
      commercial_use: "To be confirmed"
      attribution_required: true
      source: "Alibaba DAMO Academy"
      compliance_status: "Pending Review"
      legal_review_date: null
    
    qwen_7b:
      version: "Qwen3-7B-Chat-INT4-20240820"
      license: "Tongyi Qianwen License"
      commercial_use: "To be confirmed"
      attribution_required: true
      source: "Alibaba DAMO Academy"
      compliance_status: "Pending Review"
      legal_review_date: null
    
  ocr_models:
    paddle_ocr:
      version: "2.7.3"
      license: "Apache 2.0"
      commercial_use: true
      attribution_required: true
      source: "Baidu PaddlePaddle"
      compliance_status: "Approved"
      legal_review_date: "2025-08-17"
    
    umi_ocr:
      version: "2.1.2"
      license: "MIT"
      commercial_use: true
      attribution_required: true
      source: "GitHub Open Source Project"
      compliance_status: "Approved"
      legal_review_date: "2025-08-17"
```

#### License Compliance Checker

```python
# utils/license_compliance.py
"""
License compliance checker.
"""

import yaml
import requests
from typing import Dict, List
from dataclasses import dataclass
from enum import Enum

class ComplianceStatus(Enum):
    APPROVED = "Approved"
    PENDING = "Pending Review"
    UNDER_REVIEW = "Under Review"
    REJECTED = "Rejected"
    REQUIRES_LEGAL = "Requires Legal Review"

@dataclass
class LicenseInfo:
    """License information"""
    name: str
    version: str
    license: str
    commercial_use: bool
    attribution_required: bool
    source: str
    compliance_status: ComplianceStatus
    legal_review_date: str = None
    restrictions: List[str] = None

class LicenseComplianceChecker:
    """License compliance checker"""
  
    def __init__(self, config_file: str = "ai_model_licenses.yaml"):
        self.config = self.load_license_config(config_file)
        self.approved_licenses = {
            "Apache 2.0", "MIT", "BSD-3-Clause", "GPL-3.0"
        }
        self.restricted_licenses = {
            "GPL-2.0", "AGPL-3.0", "Commercial"
        }
      
    def check_all_dependencies(self) -> Dict:
        """Check license compliance for all dependencies"""
        results = {
            'ai_models': self.check_ai_models(),
            'python_packages': self.check_python_packages(),
            'system_components': self.check_system_components(),
            'overall_compliance': None
        }
      
        # Calculate overall compliance status
        results['overall_compliance'] = self.calculate_overall_compliance(results)
      
        return results
      
    def check_ai_models(self) -> List[Dict]:
        """Check AI model licenses"""
        model_results = []
      
        for category, models in self.config['ai_model_licenses'].items():
            for model_name, info in models.items():
                compliance_result = self.evaluate_model_compliance(model_name, info)
                model_results.append(compliance_result)
              
        return model_results
      
    def evaluate_model_compliance(self, model_name: str, info: Dict) -> Dict:
        """Evaluate a single model's compliance"""
        risk_level = "Low"
        issues = []
      
        # Check commercial use permission
        if info.get('commercial_use') != True:
            risk_level = "High"
            issues.append("Commercial use rights are unclear")
          
        # Check license type
        license_name = info.get('license', '')
        if license_name not in self.approved_licenses:
            if license_name in self.restricted_licenses:
                risk_level = "High"
                issues.append(f"Restrictive license: {license_name}")
            else:
                risk_level = "Medium"
                issues.append(f"Unknown license type: {license_name}")
              
        # Check legal review status
        if info.get('compliance_status') in ['Pending Review', 'Under Review']:
            risk_level = "Medium"
            issues.append("Awaiting legal review")
          
        return {
            'model_name': model_name,
            'license': license_name,
            'risk_level': risk_level,
            'compliance_status': info.get('compliance_status'),
            'issues': issues,
            'recommendation': self.generate_recommendation(risk_level, issues)
        }
      
    def generate_compliance_report(self) -> str:
        """Generate a compliance report"""
        results = self.check_all_dependencies()
      
        report = f"""
# ADG Platform - Dependency License Compliance Report

**Generation Time**: {datetime.now().isoformat()}
**Scope**: AI Models, Python Packages, System Components

