using System.ComponentModel.DataAnnotations;

namespace FWCycleDashboard.Data;

public class MachineGroup
{
    public int Id { get; set; }

    [Required]
    [StringLength(100)]
    public string Name { get; set; } = string.Empty;

    [StringLength(500)]
    public string? Description { get; set; }

    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    // Legacy single-group relationship (backward compatibility)
    public ICollection<Machine> Machines { get; set; } = new List<Machine>();

    // Many-to-many relationship with machines
    public ICollection<Machine> MachinesInGroup { get; set; } = new List<Machine>();
}
