from typing import Any, Callable

from pandasai.ee.helpers.query_builder import QueryBuilder
from pandasai.helpers.logger import Logger
from pandasai.pipelines.base_logic_unit import BaseLogicUnit
from pandasai.pipelines.logic_unit_output import LogicUnitOutput
from pandasai.pipelines.pipeline_context import PipelineContext


class CodeGenerator(BaseLogicUnit):
    """
    LLM Code Generation Stage
    """

    def __init__(
        self, on_code_generation: Callable[[str, Exception], None] = None, **kwargs
    ):
        super().__init__(**kwargs)
        self.on_code_generation = on_code_generation

    def execute(self, input: Any, **kwargs) -> Any:
        """
        This method will return output according to
        Implementation.

        :param input: Your input data.
        :param kwargs: A dictionary of keyword arguments.
            - 'logger' (any): The logger for logging.
            - 'config' (Config): Global configurations for the test
            - 'context' (any): The execution context.

        :return: The result of the execution.
        """
        pipeline_context: PipelineContext = kwargs.get("context")
        logger: Logger = kwargs.get("logger")
        schema = pipeline_context.get("df_schema")
        query_builder = QueryBuilder(schema)

        sql_query = query_builder.generate_sql(input)

        response_type = self._get_type(input)

        gen_code = self._generate_code(response_type, input)

        code = f"""
{"import matplotlib.pyplot as plt" if response_type == "plot" else ""}
import pandas as pd

sql_query="{sql_query}"
data = execute_sql_query(sql_query)

{gen_code}
"""

        logger.log(f"""Code Generated: {code}""")

        # Implement error handling pipeline here...

        return LogicUnitOutput(
            code,
            True,
            "Code Generated Successfully",
            {"content_type": "string", "value": code},
        )

    def _get_type(self, input: dict) -> bool:
        return "number" if input["type"] == "number" else "plot"

    def _generate_code(self, type, query):
        if type == "number":
            code = self._generate_code_for_number(query)

            # Format code final output
            return f"""
result = {{"type": "number","value": {code}}}
"""
        else:
            code = self.generate_matplotlib_code(query)
            code += """

result = {"type": "plot","value": "charts.png"}"""
            return code

    def _generate_code_for_number(self, query: dict) -> str:
        value = None
        if len(query["measures"]) > 0:
            value = query["measures"][0].split(".")[1]
        else:
            value = query["dimensions"][0].split(".")[1]

        return f'data["{value}"].iloc[0]'

    def generate_matplotlib_code(self, query: dict) -> str:
        chart_type = query["type"]
        x_label = query["options"].get("xLabel", None)
        y_label = query["options"].get("yLabel", None)
        title = query["options"].get("title", None)
        legend_display = {"display": True}
        legend_position = "best"
        if "legend" in query["options"]:
            legend_display = query["options"]["legend"].get("display", None)
            legend_position = query["options"]["legend"].get("position", None)
            legend_position = (
                legend_position
                in [
                    "best",
                    "upper right",
                    "upper left",
                    "lower left",
                    "lower right",
                    "right",
                    "center left",
                    "center right",
                    "lower center",
                    "upper center",
                    "center",
                ]
                or "best"
            )

        code = ""

        code_generators = {
            "bar": self._generate_bar_code,
            "line": self._generate_line_code,
            "pie": self._generate_pie_code,
            "scatter": self._generate_scatter_code,
            "hist": self._generate_hist_code,
            "histogram": self._generate_hist_code,
            "box": self._generate_box_code,
            "boxplot": self._generate_box_code,
        }

        code_generator = code_generators.get(chart_type, lambda query: "")
        code += code_generator(query)

        if x_label:
            code += f"plt.xlabel('{x_label}')\n"
        if y_label:
            code += f"plt.ylabel('{y_label}')\n"
        if title:
            code += f"plt.title('{title}')\n"

        if legend_display:
            code += f"plt.legend(loc='{legend_position}')\n"

        code += """

plt.savefig("charts.png")"""

        return code

    def _generate_bar_code(self, query):
        x_key = query["dimensions"][0].split(".")[1]
        plots = ""
        for measure in query["measures"]:
            if isinstance(measure, str):
                field_name = measure.split(".")[1]
                label = field_name
            else:
                field_name = measure["id"].split(".")[1]
                label = measure["label"]

            plots += (
                f"""plt.bar(data["{x_key}"], data["{field_name}"], label="{label}")\n"""
            )

        return plots

    def _generate_pie_code(self, query):
        dimension = query["dimensions"][0].split(".")[1]
        measure = query["measures"][0].split(".")[1]
        return f"""plt.pie(data["{measure}"], labels=data["{dimension}"], autopct='%1.1f%%')\n"""

    def _generate_line_code(self, query):
        x_key = query["dimensions"][0].split(".")[1]
        plots = ""
        for measure in query["measures"]:
            field_name = measure.split(".")[1]
            plots += f"""plt.plot(data["{x_key}"], data["{field_name}"])\n"""

        return plots

    def _generate_scatter_code(self, query):
        x_key = query["dimensions"][0].split(".")[1]
        y_key = query["dimensions"][1].split(".")[1]
        return f"plt.scatter(data['{x_key}'], data['{y_key}'])\n"

    def _generate_hist_code(self, query):
        y_key = query["measures"][0].split(".")[1]
        return f"plt.hist(data['{y_key}'])\n"

    def _generate_box_code(self, query):
        y_key = query["measures"][0].split(".")[1]
        return f"plt.boxplot(data['{y_key}'])\n"
