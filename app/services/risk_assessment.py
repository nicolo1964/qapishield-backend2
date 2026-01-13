"""
Risk assessment and AI care plan generation service
"""
import json
from typing import Dict, Tuple
from app.models.models import RiskLevel

def calculate_fall_risk(risk_factors: dict) -> Tuple[RiskLevel, float, list]:
    """Calculate fall risk based on risk factors"""
    score = 0
    recommendations = []
    
    # History of falls
    if risk_factors.get("history_of_falls"):
        score += 25
        recommendations.append("Implement 1:1 monitoring during high-risk periods")
    
    # Mobility issues
    if risk_factors.get("mobility_impairment"):
        score += 20
        recommendations.append("Physical therapy consultation for gait training")
    
    # Medications
    if risk_factors.get("psychotropic_medications"):
        score += 15
        recommendations.append("Review psychotropic medications with physician")
    
    # Cognitive impairment
    if risk_factors.get("cognitive_impairment"):
        score += 15
        recommendations.append("Bed/chair alarm system implementation")
    
    # Age factor
    age = risk_factors.get("age", 0)
    if age >= 85:
        score += 10
    elif age >= 75:
        score += 5
    
    # Environmental factors
    if risk_factors.get("poor_lighting"):
        score += 5
        recommendations.append("Improve lighting in room and hallways")
    
    # Determine risk level
    if score >= 60:
        risk_level = RiskLevel.HIGH
    elif score >= 30:
        risk_level = RiskLevel.MODERATE
    else:
        risk_level = RiskLevel.LOW
    
    if not recommendations:
        recommendations.append("Continue current fall prevention protocols")
    
    return risk_level, score, recommendations

def calculate_pressure_ulcer_risk(risk_factors: dict) -> Tuple[RiskLevel, float, list]:
    """Calculate pressure ulcer risk based on Braden-like scoring"""
    score = 0
    recommendations = []
    
    # Mobility
    if risk_factors.get("immobile"):
        score += 30
        recommendations.append("Turn and reposition every 2 hours")
        recommendations.append("Pressure-relieving mattress required")
    elif risk_factors.get("limited_mobility"):
        score += 15
        recommendations.append("Reposition every 3-4 hours")
    
    # Nutrition
    if risk_factors.get("poor_nutrition"):
        score += 20
        recommendations.append("Dietary consultation for protein supplementation")
    
    # Incontinence
    if risk_factors.get("incontinence"):
        score += 15
        recommendations.append("Implement moisture management protocol")
    
    # Existing pressure injuries
    if risk_factors.get("existing_pressure_injury"):
        score += 25
        recommendations.append("Wound care specialist consultation")
    
    # Diabetes
    if risk_factors.get("diabetes"):
        score += 10
        recommendations.append("Monitor blood glucose levels closely")
    
    # Determine risk level
    if score >= 60:
        risk_level = RiskLevel.HIGH
    elif score >= 30:
        risk_level = RiskLevel.MODERATE
    else:
        risk_level = RiskLevel.LOW
    
    if not recommendations:
        recommendations.append("Continue current skin integrity monitoring")
    
    return risk_level, score, recommendations

def calculate_infection_risk(risk_factors: dict) -> Tuple[RiskLevel, float, list]:
    """Calculate infection/sepsis risk"""
    score = 0
    recommendations = []
    
    # Immunocompromised
    if risk_factors.get("immunocompromised"):
        score += 30
        recommendations.append("Enhanced infection control precautions")
    
    # Recent hospitalization
    if risk_factors.get("recent_hospitalization"):
        score += 20
        recommendations.append("Monitor vital signs closely for 14 days")
    
    # Indwelling devices
    if risk_factors.get("catheter"):
        score += 15
        recommendations.append("Daily catheter care and removal assessment")
    
    if risk_factors.get("feeding_tube"):
        score += 10
        recommendations.append("Feeding tube site care protocol")
    
    # Wounds
    if risk_factors.get("open_wounds"):
        score += 15
        recommendations.append("Wound care with sterile technique")
    
    # COPD/respiratory
    if risk_factors.get("respiratory_condition"):
        score += 10
        recommendations.append("Respiratory therapy and monitoring")
    
    # Determine risk level
    if score >= 60:
        risk_level = RiskLevel.HIGH
    elif score >= 30:
        risk_level = RiskLevel.MODERATE
    else:
        risk_level = RiskLevel.LOW
    
    if not recommendations:
        recommendations.append("Continue standard infection control protocols")
    
    return risk_level, score, recommendations

def calculate_readmission_risk(risk_factors: dict) -> Tuple[RiskLevel, float, list]:
    """Calculate hospital readmission risk"""
    score = 0
    recommendations = []
    
    # Recent discharge
    days_since_discharge = risk_factors.get("days_since_discharge", 999)
    if days_since_discharge <= 7:
        score += 30
        recommendations.append("Daily clinical monitoring for 30 days post-discharge")
    elif days_since_discharge <= 30:
        score += 15
    
    # Multiple comorbidities
    comorbidity_count = risk_factors.get("comorbidity_count", 0)
    if comorbidity_count >= 5:
        score += 25
    elif comorbidity_count >= 3:
        score += 15
    
    # Medication complexity
    medication_count = risk_factors.get("medication_count", 0)
    if medication_count >= 10:
        score += 15
        recommendations.append("Pharmacist medication reconciliation")
    
    # Poor adherence history
    if risk_factors.get("poor_adherence"):
        score += 20
        recommendations.append("Enhanced medication administration monitoring")
    
    # Social factors
    if risk_factors.get("limited_family_support"):
        score += 10
        recommendations.append("Social work consultation")
    
    # Determine risk level
    if score >= 60:
        risk_level = RiskLevel.HIGH
    elif score >= 30:
        risk_level = RiskLevel.MODERATE
    else:
        risk_level = RiskLevel.LOW
    
    if not recommendations:
        recommendations.append("Continue standard post-hospitalization monitoring")
    
    return risk_level, score, recommendations

def assess_risk(assessment_type: str, risk_factors: dict) -> Tuple[RiskLevel, float, str, str]:
    """
    Main risk assessment function
    Returns: (risk_level, risk_score, risk_factors_json, recommendations_json)
    """
    if assessment_type == "falls":
        risk_level, score, recommendations = calculate_fall_risk(risk_factors)
    elif assessment_type == "pressure_ulcers":
        risk_level, score, recommendations = calculate_pressure_ulcer_risk(risk_factors)
    elif assessment_type == "infection":
        risk_level, score, recommendations = calculate_infection_risk(risk_factors)
    elif assessment_type == "readmission":
        risk_level, score, recommendations = calculate_readmission_risk(risk_factors)
    else:
        raise ValueError(f"Unknown assessment type: {assessment_type}")
    
    return (
        risk_level,
        score,
        json.dumps(risk_factors),
        json.dumps(recommendations)
    )

def generate_care_plan(assessment_type: str, risk_level: RiskLevel, risk_factors: dict, recommendations: list) -> str:
    """
    Generate AI-powered care plan text (placeholder implementation)
    In production, this would call an LLM API
    """
    care_plan_templates = {
        "falls": {
            RiskLevel.HIGH: """
FALL PREVENTION CARE PLAN - HIGH RISK

Assessment: Resident presents with multiple fall risk factors requiring intensive intervention.

Interventions:
1. Implement bed/chair alarm system - check functionality every shift
2. Ensure call light within reach at all times
3. Maintain clutter-free environment with clear pathways
4. Non-skid footwear required for all mobility
5. Assist with all transfers and ambulation
6. Toileting schedule every 2 hours while awake
7. Physical therapy consultation for gait assessment
8. Review medications with physician for fall risk

Monitoring:
- Document all mobility activities
- Report any near-falls or falls immediately
- Reassess fall risk weekly or with condition change

Goals:
- Zero falls during this care plan period
- Improve mobility and strength through PT
- Reduce fall risk factors within 30 days
""",
            RiskLevel.MODERATE: """
FALL PREVENTION CARE PLAN - MODERATE RISK

Assessment: Resident has some fall risk factors requiring monitoring and intervention.

Interventions:
1. Ensure call light within reach
2. Maintain clear pathways and adequate lighting
3. Non-skid footwear during ambulation
4. Supervise transfers as needed
5. Regular toileting schedule
6. Encourage use of assistive devices

Monitoring:
- Document mobility status each shift
- Report any changes in condition
- Reassess fall risk monthly

Goals:
- Prevent falls through environmental safety
- Maintain current mobility level
- Address modifiable risk factors
""",
            RiskLevel.LOW: """
FALL PREVENTION CARE PLAN - LOW RISK

Assessment: Resident has minimal fall risk factors.

Interventions:
1. Standard fall prevention protocols
2. Call light within reach
3. Encourage independence with safety awareness
4. Maintain clear environment

Monitoring:
- Routine safety rounds
- Reassess fall risk quarterly

Goals:
- Maintain low risk status
- Support independent mobility
"""
        },
        "pressure_ulcers": {
            RiskLevel.HIGH: """
PRESSURE INJURY PREVENTION CARE PLAN - HIGH RISK

Assessment: Resident at high risk for pressure injury development requiring intensive preventive measures.

Interventions:
1. Turn and reposition every 2 hours using turn schedule
2. Pressure-relieving mattress/cushion in place
3. Skin assessment with every turn - document findings
4. Keep skin clean and dry - barrier cream as needed
5. Heels off bed surface at all times (pillow under calves)
6. Nutritional supplementation per dietitian
7. Maintain head of bed <30 degrees when possible
8. Minimize shearing during transfers

Monitoring:
- Full skin assessment weekly by RN
- Document turning schedule compliance
- Monitor nutritional intake
- Report any skin changes immediately

Goals:
- Zero pressure injuries developed
- Maintain skin integrity
- Improve nutritional status within 30 days
""",
            RiskLevel.MODERATE: """
PRESSURE INJURY PREVENTION CARE PLAN - MODERATE RISK

Assessment: Resident has some risk factors for pressure injury.

Interventions:
1. Reposition every 3-4 hours
2. Skin assessment daily
3. Keep skin clean and dry
4. Encourage adequate nutrition and hydration
5. Use of pressure-relieving devices as needed

Monitoring:
- Skin assessment weekly
- Document repositioning
- Monitor risk factors

Goals:
- Prevent pressure injury development
- Maintain skin integrity
""",
            RiskLevel.LOW: """
PRESSURE INJURY PREVENTION CARE PLAN - LOW RISK

Assessment: Resident has minimal pressure injury risk.

Interventions:
1. Standard skin care protocols
2. Encourage mobility and position changes
3. Maintain adequate nutrition

Monitoring:
- Routine skin assessment
- Reassess risk monthly

Goals:
- Maintain healthy skin integrity
"""
        },
        "infection": {
            RiskLevel.HIGH: """
INFECTION PREVENTION CARE PLAN - HIGH RISK

Assessment: Resident at high risk for infection/sepsis requiring enhanced monitoring.

Interventions:
1. Enhanced hand hygiene before/after all resident contact
2. Vital signs every 4 hours - report abnormalities immediately
3. Monitor for signs of infection (fever, confusion, lethargy)
4. Indwelling device care per protocol
5. Wound care with sterile technique
6. Respiratory therapy as ordered
7. Isolation precautions if indicated

Monitoring:
- Daily assessment for infection signs
- Temperature monitoring
- Laboratory values review
- Report changes immediately to physician

Goals:
- Prevent healthcare-associated infections
- Early detection and treatment of infections
- Reduce infection risk factors
""",
            RiskLevel.MODERATE: """
INFECTION PREVENTION CARE PLAN - MODERATE RISK

Assessment: Resident has some infection risk factors.

Interventions:
1. Standard infection control precautions
2. Hand hygiene protocols
3. Monitor vital signs per routine
4. Device care per protocol
5. Encourage hydration and nutrition

Monitoring:
- Routine infection surveillance
- Report signs of infection
- Monitor risk factors

Goals:
- Prevent infections
- Maintain immune health
""",
            RiskLevel.LOW: """
INFECTION PREVENTION CARE PLAN - LOW RISK

Assessment: Resident has minimal infection risk.

Interventions:
1. Standard infection control protocols
2. Hand hygiene
3. Routine monitoring

Monitoring:
- Standard surveillance
- Reassess risk as needed

Goals:
- Maintain low infection risk
"""
        },
        "readmission": {
            RiskLevel.HIGH: """
HOSPITAL READMISSION PREVENTION CARE PLAN - HIGH RISK

Assessment: Resident at high risk for hospital readmission requiring intensive monitoring.

Interventions:
1. Daily clinical assessment by RN for 30 days post-discharge
2. Medication reconciliation and adherence monitoring
3. Vital signs every 4 hours for first week
4. Follow all hospital discharge instructions
5. Physician follow-up within 7 days
6. Pharmacist medication review
7. Social work assessment for support needs
8. Care conference with family within 48 hours

Monitoring:
- Daily documentation of clinical status
- Medication administration verification
- Report any decline immediately
- Weekly care team review

Goals:
- Prevent hospital readmission
- Optimize medication management
- Address all post-hospitalization needs
- Stabilize chronic conditions
""",
            RiskLevel.MODERATE: """
HOSPITAL READMISSION PREVENTION CARE PLAN - MODERATE RISK

Assessment: Resident has some readmission risk factors.

Interventions:
1. Regular clinical monitoring
2. Medication adherence support
3. Follow discharge instructions
4. Physician follow-up as scheduled
5. Monitor chronic conditions

Monitoring:
- Routine clinical assessment
- Medication review
- Report changes in condition

Goals:
- Prevent readmission
- Maintain stability
""",
            RiskLevel.LOW: """
HOSPITAL READMISSION PREVENTION CARE PLAN - LOW RISK

Assessment: Resident has minimal readmission risk.

Interventions:
1. Standard post-hospitalization monitoring
2. Medication administration per orders
3. Routine clinical care

Monitoring:
- Standard assessment
- Follow-up as scheduled

Goals:
- Maintain stability
- Support recovery
"""
        }
    }
    
    # Get template based on assessment type and risk level
    template = care_plan_templates.get(assessment_type, {}).get(
        risk_level,
        "Care plan template not available for this assessment type and risk level."
    )
    
    # Add specific recommendations
    recommendations_text = "\n".join([f"- {rec}" for rec in recommendations])
    
    care_plan = f"{template}\n\nAdditional Recommendations:\n{recommendations_text}"
    
    return care_plan
