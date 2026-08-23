def find_frontiers(equations, edges):
    """
    Find the latest equation in every reasoning chain.

    A frontier is any equation that has no valid outgoing edge.

    This also supports standalone equations.

    Example:

        3x+1=0
            ↓
        3x=-1      <- frontier

        2x=5       <- standalone frontier
    """

    outgoing = {
        eq["id"]: []
        for eq in equations
    }

    incoming = {
        eq["id"]: []
        for eq in equations
    }

    for edge in edges:
        source_id = edge["from"]
        target_id = edge["to"]

        if source_id in outgoing:
            outgoing[source_id].append(edge)

        if target_id in incoming:
            incoming[target_id].append(edge)

    frontiers = []

    for equation in equations:
        equation_id = equation["id"]

        has_child = len(outgoing[equation_id]) > 0

        # Any sink node is a frontier.
        if not has_child:
            frontiers.append(equation)

    return frontiers