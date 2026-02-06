import base64
from pathlib import Path

import litellm



class PolicyAgent:
    def __init__(self) -> None:
        with Path("2026AnthemgHIPSBC.pdf").open("rb") as file:
            self.pdf_data = base64.standard_b64encode(file.read()).decode("utf-8")

    def answer_query_gpt_40(self, prompt: str) -> str:
        response = litellm.completion(
            #model="gpt-4o",
            # model="gemini/gemini-3-flash-preview",
            # # For Vertex AI
            # #model="vertex_ai/gemini-3-flash-preview",
            # reasoning_effort="minimal",
            # max_tokens=1000,
            model="gemini/gemini-3-flash-preview",
            # For Vertex AI
            # model="vertex_ai/gemini-3-flash-preview",
           # reasoning_effort="minimal",
            max_tokens=1000,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert insurance agent designed to assist with coverage queries. Use the provided documents to answer questions about insurance policies. If the information is not available in the documents, respond with 'I don't know'",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:application/pdf;base64,{self.pdf_data}"
                            },
                        },
                    ],
                },
            ],
        )

        return response.choices[0].message.content.replace("$", r"\$")
    def answer_query(self, prompt: str) -> str:
        # response = litellm.completion(
        #     #model="gpt-4o",
        #     # model="gemini/gemini-3-flash-preview",
        #     # # For Vertex AI
        #     # #model="vertex_ai/gemini-3-flash-preview",
        #     # reasoning_effort="minimal",
        #     # max_tokens=1000,
        #     model="gemini/gemini-3-flash-preview",
        #     # For Vertex AI
        #     # model="vertex_ai/gemini-3-flash-preview",
        #    # reasoning_effort="minimal",
        #     max_tokens=1000,
        #     messages=[
        #         {
        #             "role": "system",
        #             "content": "You are an expert insurance agent designed to assist with coverage queries. Use the provided documents to answer questions about insurance policies. If the information is not available in the documents, respond with 'I don't know'",
        #         },
        #         {
        #             "role": "user",
        #             "content": [
        #                 {"type": "text", "text": prompt},
        #                 {
        #                     "type": "image_url",
        #                     "image_url": {
        #                         "url": f"data:application/pdf;base64,{self.pdf_data}"
        #                     },
        #                 },
        #             ],
        #         },
        #     ],
        # )
        response = litellm.completion(
            model="bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            #model="bedrock/us.anthropic.claude-3-5-sonnet-20240620-v1:0",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": self.pdf_data
                            }
                        }
                    ],
                }
            ],
            max_tokens=1000,
        )
        return response.choices[0].message.content.replace("$", r"\$")
    

# if __name__ == "__main__":
#     agent = PolicyAgent()
#     query = "What is the coverage limit for personal property under the homeowners insurance policy?"
#     answer = agent.answer_query(query)
#     print("Q:", query)
#     print("A:", answer)