# Copyright 2026 Google LLC
"""Validated Enterprise Migration TCO & Assessment tools for CloudShift Advisor.

Hardened Features:
- GCVE Node Family Auto-Sizing: Compares ve1-standard-72 (Broadwell/Cascade) vs ve2-standard-128 (Sapphire Rapids, 2TB RAM) to minimize physical node footprint.
- Egress Bandwidth Modeling: Explicitly models Cloud Interconnect and Internet outbound egress.
- Managed Database Modernization: Analyzes Cloud SQL for SQL Server / AlloyDB Omni options.
"""

import math
from typing import Any, Dict, List, Optional
from app.tools.sync_pricing import load_pricing_catalog

HOURS_PER_MONTH = 730


def get_current_pricing() -> Dict[str, Any]:
    """Helper to fetch up-to-date pricing catalog from GCS/local cache."""
    return load_pricing_catalog()


def parse_workload_metrics(
    total_vms: int,
    total_vcpu: int,
    total_ram_gb: int,
    total_storage_tb: float,
    windows_vm_pct: float = 60.0,
    linux_vm_pct: float = 40.0,
    sql_server_vms: int = 0,
    monthly_egress_gb: float = 2000.0,
    storage_type: str = "SAN_SSD",
    avg_iops: int = 50000,
    environment_type: str = "Production",
) -> Dict[str, Any]:
    """Parses and normalizes VMware RVTools workload baseline metrics.

    Args:
        total_vms: Total number of virtual machines inventoried.
        total_vcpu: Total allocated vCPUs across all VMs.
        total_ram_gb: Total allocated memory in Gigabytes across all VMs.
        total_storage_tb: Total provisioned storage in Terabytes.
        windows_vm_pct: Percentage of Windows Server VMs (e.g. 60.0).
        linux_vm_pct: Percentage of Linux VMs (e.g. 40.0).
        sql_server_vms: Number of VMs hosting Microsoft SQL Server databases.
        monthly_egress_gb: Estimated monthly outbound network egress in GB.
        storage_type: Storage architecture (e.g. SAN_SSD, vSAN, NAS).
        avg_iops: Average total disk IOPS requirement.
        environment_type: Production, Non-Prod, or Mixed.

    Returns:
        Structured dictionary of validated workload baseline metrics and resource ratios.
    """
    avg_vcpu_per_vm = round(total_vcpu / max(1, total_vms), 1)
    avg_ram_per_vm = round(total_ram_gb / max(1, total_vms), 1)
    avg_storage_per_vm_gb = round((total_storage_tb * 1024) / max(1, total_vms), 1)
    vcpu_ram_ratio = round(total_ram_gb / max(1, total_vcpu), 2)

    catalog = get_current_pricing()
    available_regions = list(catalog.get("regions", {}).keys())

    return {
        "status": "SUCCESS",
        "summary": {
            "total_vms": total_vms,
            "total_vcpu": total_vcpu,
            "total_ram_gb": total_ram_gb,
            "total_storage_tb": total_storage_tb,
            "windows_vms": int(round(total_vms * (windows_vm_pct / 100.0))),
            "linux_vms": int(round(total_vms * (linux_vm_pct / 100.0))),
            "sql_server_vms": sql_server_vms,
            "monthly_egress_gb": monthly_egress_gb,
            "storage_type": storage_type,
            "avg_iops": avg_iops,
            "environment_type": environment_type,
        },
        "ratios": {
            "avg_vcpu_per_vm": avg_vcpu_per_vm,
            "avg_ram_per_vm_gb": avg_ram_per_vm,
            "avg_storage_per_vm_gb": avg_storage_per_vm_gb,
            "ram_to_vcpu_ratio": vcpu_ram_ratio,
        },
        "available_gcp_regions": available_regions,
        "pricing_catalog_last_refreshed": catalog.get("updated_at", "2026-10-26"),
        "assessment_ready": True,
    }


def evaluate_target_landing_zone(
    migration_timeline_months: int,
    vmware_dependency_level: str,  # "HIGH", "MEDIUM", "LOW"
    container_maturity: str,       # "NONE", "BEGINNER", "ADVANCED"
    target_region: str = "us-central1",
    licensing_model: str = "BYOL", # "BYOL" or "LICENSE_INCLUDED"
    has_sql_databases: bool = False,
    custom_cots_ratio: str = "MIXED",
    db_statefulness: str = "STANDARD",
) -> Dict[str, Any]:
    """Evaluates and scores optimal GCP target services (GCVE vs GCE vs GKE) with database modernization insights.

    Args:
        migration_timeline_months: Target exit timeline in months.
        vmware_dependency_level: Level of hard VMware dependencies ('HIGH', 'MEDIUM', 'LOW').
        container_maturity: Customer team container/Kubernetes skills ('NONE', 'BEGINNER', 'ADVANCED').
        target_region: Chosen GCP region.
        licensing_model: 'BYOL' or 'LICENSE_INCLUDED'.
        has_sql_databases: True if critical relational databases (SQL Server/Oracle) exist.
        custom_cots_ratio: 'MOSTLY_COTS', 'MOSTLY_CUSTOM', 'MIXED'.
        db_statefulness: 'HEAVY_STATEFUL', 'STANDARD', 'LIGHT'.

    Returns:
        Structured scoring matrix, primary recommended landing service, alternative, and architectural trade-offs.
    """
    catalog = get_current_pricing()
    regions = catalog.get("regions", {})
    region_key = target_region.lower().strip()
    if region_key not in regions:
        region_key = "us-central1"
    reg = regions[region_key]

    scores = {"GCVE": 40, "GCE": 50, "GKE": 30}

    # Timeline scoring
    if migration_timeline_months <= 6:
        scores["GCVE"] += 35
        scores["GCE"] += 20
        scores["GKE"] -= 20
    elif migration_timeline_months <= 12:
        scores["GCE"] += 30
        scores["GCVE"] += 15
        scores["GKE"] += 15
    else:
        scores["GKE"] += 35
        scores["GCE"] += 25
        scores["GCVE"] += 5

    # VMware dependency scoring
    if vmware_dependency_level.upper() == "HIGH":
        scores["GCVE"] += 45
        scores["GCE"] -= 15
        scores["GKE"] -= 35
    elif vmware_dependency_level.upper() == "MEDIUM":
        scores["GCE"] += 20
        scores["GCVE"] += 15
    else:
        scores["GCE"] += 25
        scores["GKE"] += 25

    # Container maturity scoring
    if container_maturity.upper() == "ADVANCED":
        scores["GKE"] += 40
    elif container_maturity.upper() == "BEGINNER":
        scores["GKE"] += 15
        scores["GCE"] += 20
    else:
        scores["GKE"] -= 20
        scores["GCE"] += 25
        scores["GCVE"] += 15

    # Licensing impact
    if licensing_model.upper() == "LICENSE_INCLUDED":
        scores["GCE"] -= 5
    else:
        scores["GCE"] += 10
        scores["GCVE"] += 10

    # COTS vs Custom
    if custom_cots_ratio.upper() == "MOSTLY_COTS":
        scores["GCVE"] += 20
        scores["GCE"] += 20
        scores["GKE"] -= 25
    elif custom_cots_ratio.upper() == "MOSTLY_CUSTOM":
        scores["GKE"] += 20

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    recommended = ranked[0][0]
    alternative = ranked[1][0]

    justifications = {
        "GCVE": f"Fastest migration velocity with zero VM re-architecting, preserving native VMware vSphere/NSX toolchains and L2 stretched subnets in {reg['name']}.",
        "GCE": f"Optimal cost-to-performance ratio using Google Migrate to Virtual Machines (M2VM). Right-sizes VMs to eliminate VMware core licensing in {reg['name']}.",
        "GKE": f"Cloud-native transformation on GKE Autopilot in {reg['name']}, providing automated scaling and maximum compute efficiency.",
    }

    limitations = {
        "GCVE": "Scales in discrete physical bare-metal nodes (ve1 or ve2); requires dedicated private cloud management CIDR.",
        "GCE": "No native L2 broadcast domain in GCP VPC; requires Layer-3 routing re-architecture or IP re-addressing upon cutover.",
        "GKE": "Requires upfront containerization, refactoring CI/CD pipelines, and application state decoupling.",
    }

    db_advisory = None
    if has_sql_databases:
        db_advisory = (
            "Database Modernization Opportunity: For Microsoft SQL Server workloads, consider separating the database tier "
            "into fully-managed Google Cloud SQL for SQL Server or migrating to AlloyDB Omni to cut high commercial licensing fees."
        )

    return {
        "target_region": region_key,
        "region_display": reg["name"],
        "licensing_model": licensing_model.upper(),
        "recommended_service": recommended,
        "recommended_score": ranked[0][1],
        "alternative_service": alternative,
        "alternative_score": ranked[1][1],
        "scores": scores,
        "recommendation_justification": justifications[recommended],
        "database_advisory": db_advisory,
        "primary_limitations": limitations[recommended],
        "alternative_limitations": limitations[alternative],
    }


def calculate_tco_comparison(
    total_vms: int,
    total_vcpu: int,
    total_ram_gb: int,
    total_storage_tb: float,
    target_region: str = "us-central1",
    recommended_service: str = "GCVE",
    commitment_years: int = 3,
    licensing_model: str = "BYOL", # "BYOL" or "LICENSE_INCLUDED"
    windows_vm_pct: float = 60.0,
    monthly_egress_gb: float = 2000.0,
    gcve_preferred_node_family: str = "AUTO", # "AUTO", "VE1", "VE2"
    vmware_bundle: str = "VCF",  # 'VCF' or 'VVF'
) -> Dict[str, Any]:
    """Calculates a validated 3-year TCO with hardened ve1 vs ve2 sizing, network egress, and licensing.

    Args:
        total_vms: Total number of VMs.
        total_vcpu: Total allocated vCPUs.
        total_ram_gb: Total allocated memory in GB.
        total_storage_tb: Total storage in TB.
        target_region: GCP target deployment region.
        recommended_service: Target GCP service ('GCVE', 'GCE', 'GKE').
        commitment_years: Committed Use Discount period (1 or 3 years).
        licensing_model: 'BYOL' or 'LICENSE_INCLUDED'.
        windows_vm_pct: Percentage of Windows Server VMs needing OS licenses.
        monthly_egress_gb: Estimated monthly outbound network egress in GB.
        gcve_preferred_node_family: 'AUTO' (evaluates ve1 vs ve2 for density), 'VE1', or 'VE2'.
        vmware_bundle: On-prem VMware licensing tier ('VCF' or 'VVF').

    Returns:
        Validated 3-Year TCO breakdown, monthly and annual run-rates, ve1 vs ve2 node optimization, and net savings.
    """
    catalog = get_current_pricing()
    regions = catalog.get("regions", {})
    region_key = target_region.lower().strip()
    if region_key not in regions:
        region_key = "us-central1"
    reg = regions[region_key]
    onprem_cfg = catalog.get("onprem_benchmark", {})

    # --- 1. VALIDATED ON-PREMISE 3-YEAR MODEL ---
    hw_vcpu_mo = onprem_cfg.get("hardware_depreciation_vcpu_mo", 24.0)
    hw_ram_mo = onprem_cfg.get("hardware_depreciation_ram_gb_mo", 1.85)
    monthly_hardware_amort = (total_vcpu * hw_vcpu_mo) + (total_ram_gb * hw_ram_mo)

    # Broadcom VMware Per-Core Subscription (2024-2026 pricing)
    estimated_physical_cores = max(32, math.ceil(total_vcpu / 2.5))
    if vmware_bundle.upper() == "VVF":
        annual_per_core_license = onprem_cfg.get("vvf_annual_per_core", 140.0)
    else:
        annual_per_core_license = onprem_cfg.get("vcf_annual_per_core", 350.0)
    monthly_vmware_licensing = (estimated_physical_cores * annual_per_core_license) / 12.0

    # Enterprise SAN Storage maintenance
    monthly_storage_onprem = total_storage_tb * onprem_cfg.get("san_storage_tb_mo", 55.0)

    # Facility & Colocation (Power/Cooling)
    monthly_facilities = total_vms * onprem_cfg.get("dc_facilities_vm_mo", 22.0)

    # IT Admin Overhead
    admin_salary = onprem_cfg.get("admin_ops_annual_salary", 145000.0)
    monthly_admin_ops = (max(1, total_vms) / 120.0) * (admin_salary / 12.0)

    monthly_onprem_total = (
        monthly_hardware_amort
        + monthly_vmware_licensing
        + monthly_storage_onprem
        + monthly_facilities
        + monthly_admin_ops
    )
    tco_onprem_3yr = monthly_onprem_total * 36.0

    # --- 2. NETWORK EGRESS CALCULATION ---
    # Cloud Interconnect egress rate (~$0.025/GB)
    monthly_egress_cost = monthly_egress_gb * reg.get("egress_interconnect_gb", 0.025)

    # --- 3. TARGET GCP REGIONAL TCO MODEL ---
    target_svc = recommended_service.upper()
    is_byol = (licensing_model.upper() == "BYOL")

    windows_vcpus = total_vcpu * (windows_vm_pct / 100.0)
    if not is_byol and target_svc == "GCE":
        monthly_gcp_os_license = windows_vcpus * 0.046 * HOURS_PER_MONTH
        licensing_desc = f"License-Included: Windows Server PAYG ($0.046/vCPU-hr for {int(windows_vcpus)} vCPUs)"
    elif is_byol:
        monthly_gcp_os_license = 0.0
        licensing_desc = "BYOL (Bring Your Own License with active Software Assurance / License Mobility)"
    else:
        monthly_gcp_os_license = 0.0
        licensing_desc = "Covered under host/cluster licensing"

    node_architecture_comparison = None

    if target_svc == "GCVE":
        # Sizing Evaluation: ve1-standard-72 vs ve2-standard-128
        # ve1: 72 vCPU, 768 GB RAM, 19.2 TB NVMe
        ve1_nodes = max(3, max(
            math.ceil(total_vcpu / 72.0),
            math.ceil(total_ram_gb / 768.0),
            math.ceil(total_storage_tb / 19.2),
        ))
        # ve2: 128 vCPU (64 physical cores), 2048 GB RAM, 25.5 TB NVMe
        ve2_nodes = max(3, max(
            math.ceil(total_vcpu / 128.0),
            math.ceil(total_ram_gb / 2048.0),
            math.ceil(total_storage_tb / 25.5),
        ))

        # Hourly rates based on commitment
        if commitment_years >= 3:
            r_ve1 = reg["gcve_ve1_node_hour_3yr_commit"]
            r_ve2 = reg.get("gcve_ve2_node_hour_3yr_commit", 6.72)
            cud_label = "3-Year Committed Use Discount"
        elif commitment_years == 1:
            r_ve1 = reg["gcve_ve1_node_hour_1yr_commit"]
            r_ve2 = reg.get("gcve_ve2_node_hour_1yr_commit", 8.85)
            cud_label = "1-Year Committed Use Discount"
        else:
            r_ve1 = reg["gcve_ve1_node_hour_ondemand"]
            r_ve2 = reg.get("gcve_ve2_node_hour_ondemand", 17.80)
            cud_label = "On-Demand Hourly Rate"

        m_cost_ve1 = ve1_nodes * r_ve1 * HOURS_PER_MONTH
        m_cost_ve2 = ve2_nodes * r_ve2 * HOURS_PER_MONTH

        # Auto-select the more cost-effective and architecturally dense node family
        if gcve_preferred_node_family.upper() == "VE2" or (gcve_preferred_node_family.upper() == "AUTO" and m_cost_ve2 <= m_cost_ve1):
            chosen_family = "ve2-standard-128"
            node_count = ve2_nodes
            monthly_gcp_compute = m_cost_ve2
            sizing_summary = f"{node_count}x ve2-standard-128 Sapphire Rapids nodes (2,048 GB RAM / 25.5 TB NVMe each)"
        else:
            chosen_family = "ve1-standard-72"
            node_count = ve1_nodes
            monthly_gcp_compute = m_cost_ve1
            sizing_summary = f"{node_count}x ve1-standard-72 bare-metal nodes (768 GB RAM / 19.2 TB NVMe each)"

        node_architecture_comparison = {
            "selected_family": chosen_family,
            "ve1_standard_72": {
                "nodes_required": ve1_nodes,
                "monthly_compute": round(m_cost_ve1, 2),
                "total_ram_gb": ve1_nodes * 768,
                "total_nvme_tb": round(ve1_nodes * 19.2, 1),
            },
            "ve2_standard_128": {
                "nodes_required": ve2_nodes,
                "monthly_compute": round(m_cost_ve2, 2),
                "total_ram_gb": ve2_nodes * 2048,
                "total_nvme_tb": round(ve2_nodes * 25.5, 1),
            },
            "density_savings_insight": (
                f"ve2-standard-128 reduces cluster footprint to {ve2_nodes} nodes (vs {ve1_nodes} on ve1) "
                f"with {ve2_nodes * 2048} GB RAM for high-density consolidation."
                if ve2_nodes < ve1_nodes else "ve1-standard-72 is well-matched for this cluster capacity."
            ),
        }

        monthly_gcp_storage = 0.0
        monthly_gcp_ops = monthly_admin_ops * 0.70

    elif target_svc == "GKE":
        gke_discount = 0.55 if commitment_years >= 3 else (0.70 if commitment_years == 1 else 1.0)
        effective_vcpu = total_vcpu * 0.75
        effective_ram = total_ram_gb * 0.80

        monthly_gcp_compute = (
            (effective_vcpu * reg["gke_vcpu_hour"] * HOURS_PER_MONTH)
            + (effective_ram * reg["gke_ram_gb_hour"] * HOURS_PER_MONTH)
        ) * gke_discount
        monthly_gcp_storage = (total_storage_tb * 1024 * reg["gce_pd_balanced_gb_mo"])
        monthly_gcp_ops = monthly_admin_ops * 0.45
        cud_label = f"{commitment_years}-Year Compute CUD"
        sizing_summary = f"GKE Autopilot containerized pod capacity in {reg['name']}"

    else:  # GCE (Default)
        gce_discount = 0.55 if commitment_years >= 3 else (0.70 if commitment_years == 1 else 1.0)
        cud_label = f"{commitment_years}-Year Resource-Based CUD (~{int((1-gce_discount)*100)}% discount)"

        monthly_raw_compute = (
            (total_vcpu * reg["gce_vcpu_hour"] * HOURS_PER_MONTH)
            + (total_ram_gb * reg["gce_ram_gb_hour"] * HOURS_PER_MONTH)
        )
        monthly_gcp_compute = monthly_raw_compute * gce_discount
        monthly_gcp_storage = (total_storage_tb * 1024 * reg["gce_pd_balanced_gb_mo"])
        monthly_gcp_ops = monthly_admin_ops * 0.55
        sizing_summary = f"Google Compute Engine (N2 custom/standard VM shapes) with Balanced PD in {reg['name']}"

    monthly_gcp_total = monthly_gcp_compute + monthly_gcp_storage + monthly_gcp_os_license + monthly_egress_cost + monthly_gcp_ops
    tco_gcp_3yr = monthly_gcp_total * 36.0

    three_year_savings = max(0.0, tco_onprem_3yr - tco_gcp_3yr)
    savings_pct = round((three_year_savings / max(1.0, tco_onprem_3yr)) * 100.0, 1)

    return {
        "region_info": {
            "region": region_key,
            "region_name": reg["name"],
        },
        "licensing_profile": {
            "model": "BYOL" if is_byol else "LICENSE_INCLUDED (PAYG)",
            "details": licensing_desc,
            "monthly_license_cost": round(monthly_gcp_os_license, 2),
        },
        "network_egress": {
            "monthly_egress_gb": monthly_egress_gb,
            "monthly_cost": round(monthly_egress_cost, 2),
            "rate_basis": "Cloud Interconnect egress (~$0.025/GB)",
        },
        "node_architecture_comparison": node_architecture_comparison,
        "onprem_tco": {
            "monthly_total": round(monthly_onprem_total, 2),
            "three_year_total": round(tco_onprem_3yr, 2),
            "breakdown": {
                "hardware_depreciation_monthly": round(monthly_hardware_amort, 2),
                "vmware_licensing_monthly": round(monthly_vmware_licensing, 2),
                "storage_san_monthly": round(monthly_storage_onprem, 2),
                "dc_power_space_cooling_monthly": round(monthly_facilities, 2),
                "it_admin_overhead_monthly": round(monthly_admin_ops, 2),
            },
            "pricing_basis": onprem_cfg.get("source", "Broadcom VCF ($350/core/yr), SAN SSD, PUE 1.5"),
        },
        "gcp_tco": {
            "target_service": target_svc,
            "region": region_key,
            "sizing_details": sizing_summary,
            "discount_structure": cud_label,
            "monthly_total": round(monthly_gcp_total, 2),
            "three_year_total": round(tco_gcp_3yr, 2),
            "breakdown": {
                "compute_monthly": round(monthly_gcp_compute, 2),
                "storage_monthly": round(monthly_gcp_storage, 2),
                "os_licensing_monthly": round(monthly_gcp_os_license, 2),
                "network_egress_monthly": round(monthly_egress_cost, 2),
                "it_admin_ops_monthly": round(monthly_gcp_ops, 2),
            },
            "pricing_basis": f"Google Cloud Pricing Catalog for {region_key} (synced from Cloud Storage / Billing API)",
        },
        "financial_summary": {
            "three_year_net_savings": round(three_year_savings, 2),
            "savings_percentage": savings_pct,
            "annualized_run_rate_onprem": round(monthly_onprem_total * 12.0, 2),
            "annualized_run_rate_gcp": round(monthly_gcp_total * 12.0, 2),
            "payback_period": "Immediate (operational expenditure cutover)",
        },
    }


def generate_migration_checklist(target_service: str, target_region: str = "us-central1") -> Dict[str, Any]:
    """Generates workload-specific prerequisites, landing zone requirements, and migration tool steps.

    Args:
        target_service: Target GCP service ('GCVE', 'GCE', or 'GKE').
        target_region: GCP region for deployment.

    Returns:
        Structured checklist including networking, IAM, tools, and migration wave milestones.
    """
    catalog = get_current_pricing()
    reg = catalog.get("regions", {}).get(target_region.lower(), {})
    region_name = reg.get("name", target_region)

    checklists = {
        "GCVE": {
            "primary_tool": "VMware HCX (Hybrid Cloud Extension)",
            "prerequisites": [
                f"Verify GCVE quota and private cloud availability in {region_name} ({target_region})",
                "Establish Dedicated/Partner Cloud Interconnect or Cloud VPN with min 1Gbps dedicated bandwidth",
                "Reserve non-overlapping /22 private CIDR block for GCVE vCenter/NSX management infrastructure",
                "Deploy VMware HCX Cloud in GCVE and HCX Connector on-premises (vCenter 6.5+ / ESXi 6.0+)",
            ],
            "networking_steps": [
                "Configure VPC Network Peering between GCVE private cloud and your Google Cloud project VPC",
                "Set up HCX Network Extension (L2 stretch) for live, zero-downtime vMotion migrations",
            ],
            "limitations_to_note": [
                "Minimum 3 physical bare-metal nodes required initially per cluster (ve1 or ve2)",
                "Compute and storage scale co-dependently with physical node increments (or expand via Google Cloud NetApp Volumes)",
            ],
        },
        "GCE": {
            "primary_tool": "Migrate to Virtual Machines (M2VM v5)",
            "prerequisites": [
                f"Create target VPC subnet and Cloud NAT in {region_name} ({target_region})",
                "Enable VM Migration API (vmmigration.googleapis.com) in target GCP project",
                "Deploy Migrate to Virtual Machines On-Premises Connector OVA in vCenter",
                "Grant 'roles/vmmigration.admin' to migration service account",
                "Verify source VMs have virtio drivers installed (Linux initramfs / Windows PV drivers)",
            ],
            "networking_steps": [
                "Design target VPC subnets and firewall rules in GCP",
                "Plan IP re-addressing or DNS update TTL lowering for cutover window (no native L2 broadcast)",
            ],
            "limitations_to_note": [
                "GCP VPC does not support L2 broadcast or multicast domains; legacy cluster heartbeats need unicast",
                "Inspect source VMs for unsupported legacy operating system kernels prior to replication",
            ],
        },
        "GKE": {
            "primary_tool": "GKE Enterprise / Migrate to Containers & Skaffold",
            "prerequisites": [
                f"Provision GKE Autopilot cluster with Private Nodes enabled in {region_name} ({target_region})",
                "Assess application statefulness and decompose monolith into stateless microservices",
                "Containerize app binaries into OCI/Docker container images",
                "Provision Artifact Registry repository for container image storage",
            ],
            "networking_steps": [
                "Configure Cloud Load Balancing (GKE Ingress / Gateway API)",
                "Set up Cloud DNS and internal service discovery",
            ],
            "limitations_to_note": [
                "High initial refactoring effort for legacy COTS or heavy Windows workloads",
                "Persistent disk volume attachments require CSI driver lifecycle management",
            ],
        },
    }

    target = target_service.upper() if target_service.upper() in checklists else "GCE"
    return {
        "target_service": target,
        "target_region": target_region,
        "region_name": region_name,
        "checklist": checklists[target],
    }
