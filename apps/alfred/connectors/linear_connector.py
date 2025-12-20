"""
Linear Connector Module

A module for retrieving issues and comments from Linear.
Allows fetching issue lists and their comments with date range filtering.
"""

from datetime import datetime
from typing import Any

import requests


class LinearConnector:
    """Class for retrieving issues and comments from Linear."""

    def __init__(self, token: str | None = None):
        """
        Initialize the LinearConnector class.

        Args:
            token: Linear API token (optional, can be set later with set_token)
        """
        self.token = token
        self.api_url = "https://api.linear.app/graphql"

    def set_token(self, token: str) -> None:
        """
        Set the Linear API token.

        Args:
            token: Linear API token
        """
        self.token = token

    def get_headers(self) -> dict[str, str]:
        """
        Get headers for Linear API requests.

        Returns:
            Dictionary of headers

        Raises:
            ValueError: If no Linear token has been set
        """
        if not self.token:
            raise ValueError("Linear token not initialized. Call set_token() first.")

        return {"Content-Type": "application/json", "Authorization": self.token}

    def execute_graphql_query(
        self, query: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Execute a GraphQL query against the Linear API.

        Args:
            query: GraphQL query string
            variables: Variables for the GraphQL query (optional)

        Returns:
            Response data from the API

        Raises:
            ValueError: If no Linear token has been set
            Exception: If the API request fails
        """
        if not self.token:
            raise ValueError("Linear token not initialized. Call set_token() first.")

        headers = self.get_headers()
        payload = {"query": query}

        if variables:
            payload["variables"] = variables

        response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)

        if response.status_code != 200:
            raise RuntimeError(
                f"Query failed with status code {response.status_code}: {response.text}"
            )

        data: dict[str, Any] = response.json()
        if "errors" in data:
            messages = "; ".join(
                [err.get("message", "Unknown error") for err in data.get("errors", [])]
            )
            raise RuntimeError(f"GraphQL errors: {messages}")
        return data

    def get_all_issues(
        self, include_comments: bool = True, limit: int = 100
    ) -> list[dict[str, Any]]:
        """
        Fetch all issues from Linear.

        Args:
            include_comments: Whether to include comments in the response

        Returns:
            List of issue objects

        Raises:
            ValueError: If no Linear token has been set
            Exception: If the API request fails
        """
        comments_query = ""
        if include_comments:
            comments_query = """
            comments {
                nodes {
                    id
                    body
                    user {
                        id
                        name
                        email
                    }
                    createdAt
                    updatedAt
                }
            }
            """

        per_page = 100
        requested_limit = max(1, limit)
        all_issues: list[dict[str, Any]] = []
        cursor: str | None = None
        has_next_page = True

        query = f"""
        query Issues($after: String) {{
            issues(first: {per_page}, after: $after) {{
                nodes {{
                    id
                    identifier
                    title
                    description
                    state {{
                        id
                        name
                        type
                    }}
                    assignee {{
                        id
                        name
                        email
                    }}
                    creator {{
                        id
                        name
                        email
                    }}
                    createdAt
                    updatedAt
                    {comments_query}
                }}
                pageInfo {{
                    hasNextPage
                    endCursor
                }}
            }}
        }}
        """

        while has_next_page and len(all_issues) < requested_limit:
            variables = {"after": cursor} if cursor else {}
            result = self.execute_graphql_query(query, variables)
            issues_data = (result.get("data") or {}).get("issues") or {}
            nodes = issues_data.get("nodes") or []
            if isinstance(nodes, list):
                remaining = requested_limit - len(all_issues)
                all_issues.extend(nodes[:remaining])

            page_info = issues_data.get("pageInfo") or {}
            has_next_page = bool(page_info.get("hasNextPage"))
            cursor = page_info.get("endCursor") if has_next_page else None

            if not nodes:
                break

        return all_issues

    def get_issues_by_date_range(
        self,
        start_date: str,
        end_date: str,
        include_comments: bool = True,
        limit: int = 100,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Fetch issues within a date range.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format (inclusive)
            include_comments: Whether to include comments in the response

        Returns:
            Tuple containing (issues list, error message or None)
        """
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            if start_dt > end_dt:
                return [], "Invalid date range: start_date must be <= end_date."
        except ValueError as exc:
            return [], f"Invalid date format: {exc!s}. Please use YYYY-MM-DD."

        requested_limit = max(1, limit)
        comments_query = ""
        if include_comments:
            comments_query = """
            comments {
                nodes {
                    id
                    body
                    user {
                        id
                        name
                        email
                    }
                    createdAt
                    updatedAt
                }
            }
            """

        query = f"""
        query IssuesByDateRange($after: String) {{
            issues(
                first: 100,
                after: $after,
                filter: {{
                    or: [
                        {{
                            createdAt: {{
                                gte: "{start_date}T00:00:00Z"
                                lte: "{end_date}T23:59:59Z"
                            }}
                        }},
                        {{
                            updatedAt: {{
                                gte: "{start_date}T00:00:00Z"
                                lte: "{end_date}T23:59:59Z"
                            }}
                        }}
                    ]
                }}
            ) {{
                nodes {{
                    id
                    identifier
                    title
                    description
                    state {{
                        id
                        name
                        type
                    }}
                    assignee {{
                        id
                        name
                        email
                    }}
                    creator {{
                        id
                        name
                        email
                    }}
                    createdAt
                    updatedAt
                    {comments_query}
                }}
                pageInfo {{
                    hasNextPage
                    endCursor
                }}
            }}
        }}
        """

        try:
            all_issues: list[dict[str, Any]] = []
            has_next_page = True
            cursor: str | None = None

            while has_next_page and len(all_issues) < requested_limit:
                variables = {"after": cursor} if cursor else {}
                result = self.execute_graphql_query(query, variables)
                issues_page = (result.get("data") or {}).get("issues") or {}
                nodes = issues_page.get("nodes") or []
                if isinstance(nodes, list):
                    remaining = requested_limit - len(all_issues)
                    all_issues.extend(nodes[:remaining])

                page_info = issues_page.get("pageInfo") or {}
                has_next_page = bool(page_info.get("hasNextPage"))
                cursor = page_info.get("endCursor") if has_next_page else None

                if not nodes:
                    break

            if not all_issues:
                return [], "No issues found in the specified date range."

            return all_issues, None
        except Exception as exc:
            return [], f"Error fetching issues: {exc!s}"

    def format_issue(self, issue: dict[str, Any]) -> dict[str, Any]:
        """
        Format an issue for easier consumption.

        Args:
            issue: The issue object from Linear API

        Returns:
            Formatted issue dictionary
        """
        # Extract basic issue details
        formatted = {
            "id": issue.get("id", ""),
            "identifier": issue.get("identifier", ""),
            "title": issue.get("title", ""),
            "description": issue.get("description", ""),
            "state": issue.get("state", {}).get("name", "Unknown")
            if issue.get("state")
            else "Unknown",
            "state_type": issue.get("state", {}).get("type", "Unknown")
            if issue.get("state")
            else "Unknown",
            "created_at": issue.get("createdAt", ""),
            "updated_at": issue.get("updatedAt", ""),
            "creator": {
                "id": issue.get("creator", {}).get("id", "") if issue.get("creator") else "",
                "name": issue.get("creator", {}).get("name", "Unknown")
                if issue.get("creator")
                else "Unknown",
                "email": issue.get("creator", {}).get("email", "") if issue.get("creator") else "",
            }
            if issue.get("creator")
            else {"id": "", "name": "Unknown", "email": ""},
            "assignee": {
                "id": issue.get("assignee", {}).get("id", ""),
                "name": issue.get("assignee", {}).get("name", "Unknown"),
                "email": issue.get("assignee", {}).get("email", ""),
            }
            if issue.get("assignee")
            else None,
            "comments": [],
        }

        # Extract comments if available
        if "comments" in issue and "nodes" in issue["comments"]:
            for comment in issue["comments"]["nodes"]:
                formatted_comment = {
                    "id": comment.get("id", ""),
                    "body": comment.get("body", ""),
                    "created_at": comment.get("createdAt", ""),
                    "updated_at": comment.get("updatedAt", ""),
                    "user": {
                        "id": comment.get("user", {}).get("id", "") if comment.get("user") else "",
                        "name": comment.get("user", {}).get("name", "Unknown")
                        if comment.get("user")
                        else "Unknown",
                        "email": comment.get("user", {}).get("email", "")
                        if comment.get("user")
                        else "",
                    }
                    if comment.get("user")
                    else {"id": "", "name": "Unknown", "email": ""},
                }
                formatted["comments"].append(formatted_comment)

        return formatted

    def format_issue_to_markdown(self, issue: dict[str, Any]) -> str:
        """
        Convert an issue to markdown format.

        Args:
            issue: The issue object (either raw or formatted)

        Returns:
            Markdown string representation of the issue
        """
        # Format the issue if it's not already formatted
        if "identifier" not in issue:
            issue = self.format_issue(issue)

        # Build the markdown content
        markdown = f"# {issue.get('identifier', 'No ID')}: {issue.get('title', 'No Title')}\n\n"

        if issue.get("state"):
            markdown += f"**Status:** {issue['state']}\n\n"

        if issue.get("assignee") and issue["assignee"].get("name"):
            markdown += f"**Assignee:** {issue['assignee']['name']}\n"

        if issue.get("creator") and issue["creator"].get("name"):
            markdown += f"**Created by:** {issue['creator']['name']}\n"

        if issue.get("created_at"):
            created_date = self.format_date(issue["created_at"])
            markdown += f"**Created:** {created_date}\n"

        if issue.get("updated_at"):
            updated_date = self.format_date(issue["updated_at"])
            markdown += f"**Updated:** {updated_date}\n\n"

        if issue.get("description"):
            markdown += f"## Description\n\n{issue['description']}\n\n"

        if issue.get("comments"):
            markdown += f"## Comments ({len(issue['comments'])})\n\n"

            for comment in issue["comments"]:
                user_name = "Unknown"
                if comment.get("user") and comment["user"].get("name"):
                    user_name = comment["user"]["name"]

                comment_date = "Unknown date"
                if comment.get("created_at"):
                    comment_date = self.format_date(comment["created_at"])

                markdown += (
                    f"### {user_name} ({comment_date})\n\n{comment.get('body', '')}\n\n---\n\n"
                )

        return markdown

    @staticmethod
    def format_date(iso_date: str) -> str:
        """
        Format an ISO date string to a more readable format.

        Args:
            iso_date: ISO format date string

        Returns:
            Formatted date string
        """
        if not iso_date or not isinstance(iso_date, str):
            return "Unknown date"

        try:
            dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return iso_date
