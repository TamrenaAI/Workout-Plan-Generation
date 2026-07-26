"""
Module 3: Nutrition Agent Engine
Calculates macro distributions and constructs structured 3-meal plans (Breakfast, Lunch, Dinner).
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from api.schemas.integration_schemas import (
    NutritionSurvey, NutritionPlan, DailyMealArchitecture, MealOption
)


class NutritionEngine:
    def __init__(self):
        self._plans_db: Dict[str, NutritionPlan] = {}

    def generate_nutrition_plan(
        self,
        survey: NutritionSurvey,
        bmr_kcal: float = 1800.0,
        weight_kg: float = 80.0
    ) -> NutritionPlan:
        """Calculates macros and constructs complete Breakfast, Lunch, and Dinner meal plans."""
        goal = survey.target_goal.lower()

        # Caloric target based on goal
        if "hypertrophy" in goal or "bulk" in goal:
            target_calories = bmr_kcal * 1.55 + 300
        elif "fat_loss" in goal or "cut" in goal:
            target_calories = max(1400.0, bmr_kcal * 1.35 - 400)
        else:  # recomposition / maintenance
            target_calories = bmr_kcal * 1.45

        # Macro Breakdown (g)
        protein_g = weight_kg * 2.2  # 2.2g per kg bodyweight
        fats_g = (target_calories * 0.25) / 9.0  # 25% of calories from fat
        carbs_g = max(50.0, (target_calories - (protein_g * 4.0 + fats_g * 9.0)) / 4.0)

        # Build Meals (Breakfast, Lunch, Dinner)
        breakfast = self._build_breakfast(survey, target_calories * 0.3, protein_g * 0.3)
        lunch = self._build_lunch(survey, target_calories * 0.4, protein_g * 0.4)
        dinner = self._build_dinner(survey, target_calories * 0.3, protein_g * 0.3)

        daily_meals = DailyMealArchitecture(
            breakfast=breakfast,
            lunch=lunch,
            dinner=dinner,
            snacks=[]
        )

        plan = NutritionPlan(
            user_id=survey.user_id,
            target_calories_kcal=round(target_calories, 1),
            target_protein_g=round(protein_g, 1),
            target_carbs_g=round(carbs_g, 1),
            target_fats_g=round(fats_g, 1),
            daily_meals=daily_meals,
            generated_at=datetime.now(timezone.utc)
        )

        self._plans_db[survey.user_id] = plan
        return plan

    def get_user_plan(self, user_id: str) -> Optional[NutritionPlan]:
        return self._plans_db.get(user_id)

    def _build_breakfast(self, survey: NutritionSurvey, target_cal: float, target_prot: float) -> MealOption:
        pref = survey.dietary_preference.lower()
        if "keto" in pref:
            return MealOption(
                name="Avocado & Egg Scramble",
                calories_kcal=round(target_cal, 1),
                protein_g=round(target_prot, 1),
                carbs_g=8.0,
                fats_g=round((target_cal - target_prot * 4 - 32) / 9, 1),
                ingredients=["4 Large Eggs", "1/2 Avocado", "1 tbsp Olive Oil", "Spinach"],
                swap_options=["Omelette with Cheddar Cheese"]
            )
        return MealOption(
            name="High-Protein Oats with Berries & Whey",
            calories_kcal=round(target_cal, 1),
            protein_g=round(target_prot, 1),
            carbs_g=round((target_cal * 0.5) / 4, 1),
            fats_g=round((target_cal * 0.2) / 9, 1),
            ingredients=["80g Rolled Oats", "1 Scoop Whey Isolate", "100g Blueberries", "15g Almonds"],
            swap_options=["Greek Yogurt & Granola Bowl", "Egg White Toast with Avocado"]
        )

    def _build_lunch(self, survey: NutritionSurvey, target_cal: float, target_prot: float) -> MealOption:
        return MealOption(
            name="Grilled Chicken Breast with Quinoa & Roasted Vegetables",
            calories_kcal=round(target_cal, 1),
            protein_g=round(target_prot, 1),
            carbs_g=round((target_cal * 0.45) / 4, 1),
            fats_g=round((target_cal * 0.2) / 9, 1),
            ingredients=["200g Grilled Chicken Breast", "150g Cooked Quinoa", "Steamed Broccoli & Carrots", "1 tbsp Olive Oil Dressing"],
            swap_options=["Turkey Breast Bowl", "Tofu Stir-fry with Brown Rice"]
        )

    def _build_dinner(self, survey: NutritionSurvey, target_cal: float, target_prot: float) -> MealOption:
        return MealOption(
            name="Pan-Seared Salmon Fillet with Sweet Potato & Asparagus",
            calories_kcal=round(target_cal, 1),
            protein_g=round(target_prot, 1),
            carbs_g=round((target_cal * 0.4) / 4, 1),
            fats_g=round((target_cal * 0.25) / 9, 1),
            ingredients=["180g Salmon Fillet", "200g Baked Sweet Potato", "Grilled Asparagus Spears", "Lemon Herb Dressing"],
            swap_options=["Sirloin Steak with Potato Wedges", "White Fish with Jasmine Rice"]
        )


nutrition_engine = NutritionEngine()
